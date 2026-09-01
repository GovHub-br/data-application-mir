import logging
import io
import zipfile
from typing import Optional, Tuple, cast, List, Dict
import pandas as pd
from pandas.errors import EmptyDataError
from imap_tools import MailBox, AND
from imap_tools.message import MailMessage
import chardet
from datetime import datetime, date, timedelta
import pytz

# Configuração do log
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Timezone unico do projeto para definir "hoje" de forma consistente.
DEFAULT_TIMEZONE = "America/Sao_Paulo"
# Formato aceito nos parametros de data das DAGs (ex.: 2026-08-31).
DATE_FORMAT = "%Y-%m-%d"


def _today(tz: str = DEFAULT_TIMEZONE) -> date:
    """Data atual no timezone do projeto."""
    return datetime.now(pytz.timezone(tz)).date()


def parse_email_date_param(
    value: Optional[str], field_name: str = "data"
) -> Optional[date]:
    """Valida e converte uma data 'YYYY-MM-DD' em date.

    None (ou string vazia) passa direto como None. Qualquer outro formato
    levanta ValueError com mensagem clara, em vez de deixar o erro
    aparecer depois como uma falha obscura do IMAP.
    """
    if value is None or value == "":
        return None
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Parametro '{field_name}' invalido: '{value}'. "
            "Use o formato YYYY-MM-DD (ex.: 2026-08-31)."
        ) from exc


def resolve_email_date_range(
    data_inicial: Optional[str],
    data_final: Optional[str],
) -> Tuple[Optional[date], Optional[date]]:
    """Normaliza e valida os parametros de intervalo das DAGs.

    Ambos os parametros sao opcionais e devem estar no formato YYYY-MM-DD.
    Levanta ValueError em formato invalido ou quando data_inicial for
    posterior a data_final. Retorna (start, end) como objetos date (ou
    None), sem aplicar qualquer deslocamento — a traducao para a semantica
    do IMAP fica a cargo de build_date_criteria.
    """
    start = parse_email_date_param(data_inicial, "data_inicial")
    end = parse_email_date_param(data_final, "data_final")
    if start is not None and end is not None and start > end:
        raise ValueError(
            f"'data_inicial' ({start.isoformat()}) nao pode ser posterior a "
            f"'data_final' ({end.isoformat()})."
        )
    return start, end


def build_date_criteria(
    target_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tz: str = DEFAULT_TIMEZONE,
) -> Dict[str, date]:
    """Traduz o intervalo desejado nos kwargs de data do imap_tools.AND.

    Semantica do IMAP (usada pelo imap_tools):
      - date_gte -> SINCE: inclusivo (>= data);
      - date_lt  -> BEFORE: exclusivo (< data);
      - date     -> ON: um unico dia.
    Para um intervalo inclusivo nas duas pontas somamos 1 dia a end_date,
    de modo que BEFORE (end+1) inclua o proprio end.

    Precedencia: se start_date/end_date forem informados, o intervalo tem
    prioridade sobre target_date. Sem nenhum intervalo, mantem o
    comportamento legado — data unica (target_date) ou o dia atual.
    """
    if start_date is not None or end_date is not None:
        criteria: Dict[str, date] = {}
        if start_date is not None:
            criteria["date_gte"] = start_date
        if end_date is not None:
            criteria["date_lt"] = end_date + timedelta(days=1)
        return criteria
    return {"date": target_date or _today(tz)}


def describe_date_range(
    target_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tz: str = DEFAULT_TIMEZONE,
) -> str:
    """Descreve o intervalo solicitado em texto para os logs."""
    if start_date is None and end_date is None:
        if target_date is not None:
            return f"da data {target_date.isoformat()}"
        return f"do dia atual ({_today(tz).isoformat()})"
    if start_date is not None and end_date is not None:
        return f"de {start_date.isoformat()} ate {end_date.isoformat()}"
    if start_date is not None:
        return f"de {start_date.isoformat()} ate a data atual ({_today(tz).isoformat()})"
    return f"ate {cast(date, end_date).isoformat()}"


def _message_sort_key(msg: MailMessage) -> datetime:
    """Chave de ordenacao cronologica pela data/hora efetiva da mensagem.

    imap_tools devolve msg.date ora naive, ora com tzinfo. Normalizamos
    datas naive para o timezone do projeto para que a comparacao entre
    mensagens seja consistente e nunca quebre por mistura naive/aware.
    """
    dt = msg.date
    if dt.tzinfo is None:
        dt = pytz.timezone(DEFAULT_TIMEZONE).localize(dt)
    return dt


def _fetch_sorted_attachments(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    extension: str,
    subject: Optional[str] = None,
    subject_suffix: Optional[str] = None,
    target_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tz: str = DEFAULT_TIMEZONE,
) -> List[bytes]:
    """Busca anexos de uma extensao, filtrando por data/remetente/assunto.

    Ponto unico de comunicacao com o IMAP para as DAGs de ingestao via
    e-mail: constroi o filtro de data (single day, intervalo ou dia atual),
    aplica remetente e assunto/suffix, e devolve os anexos ja ordenados do
    mais antigo para o mais recente pela data efetiva da mensagem.

    Mantem bulk=True (um unico FETCH para todas as mensagens) para evitar
    overquota; a ordenacao guarda apenas (data, payload) — mesmo footprint
    de memoria do codigo anterior, que ja materializava os payloads.
    """
    if not subject and not subject_suffix:
        raise ValueError("subject ou subject_suffix precisa ser informado.")

    criteria = build_date_criteria(
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        tz=tz,
    )
    logging.info(
        "Buscando e-mails %s",
        describe_date_range(
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
            tz=tz,
        ),
    )

    and_kwargs: Dict[str, object] = dict(criteria)
    and_kwargs["from_"] = sender_email
    # subject exato vai no filtro IMAP; subject_suffix e filtrado no cliente
    # (IMAP nao tem "termina com").
    if subject and not subject_suffix:
        and_kwargs["subject"] = subject

    collected: List[Tuple[datetime, bytes]] = []
    matched_messages = 0
    with MailBox(imap_server).login(email, password) as mailbox:
        # bulk=True: single IMAP FETCH command for all messages (avoids overquota)
        for msg in mailbox.fetch(AND(**and_kwargs), bulk=True):
            if subject_suffix and not (msg.subject or "").endswith(subject_suffix):
                continue
            matched_messages += 1
            sort_key = _message_sort_key(msg)
            for attachment in msg.attachments:
                if (attachment.filename or "").lower().endswith(extension):
                    collected.append((sort_key, cast(bytes, attachment.payload)))

    collected.sort(key=lambda item: item[0])
    logging.info(
        "Mensagens correspondentes: %s | anexos %s encontrados: %s",
        matched_messages,
        extension,
        len(collected),
    )
    return [payload for _, payload in collected]


def format_csv(
    csv_data: str, column_mapping: Optional[Dict[int, str]], skiprows: int
) -> pd.DataFrame:
    """Formata um arquivo CSV conforme mapeamento de colunas."""
    if column_mapping:
        df = pd.read_csv(io.StringIO(csv_data), skiprows=skiprows, header=None)
        column_names: List[str] = [
            column_mapping.get(i, f"col_{i}") for i in range(len(df.columns))
        ]
        df.columns = pd.Index(column_names)
    else:
        df = pd.read_csv(io.StringIO(csv_data), skiprows=skiprows, header=0)
    return df


def extract_csv_from_zip(
    zip_payload: bytes, column_mapping: dict, skiprows: int = 0
) -> Optional[pd.DataFrame]:
    """Extrai e formata o primeiro arquivo CSV encontrado em um ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_payload)) as zip_file:
        for file_name in zip_file.namelist():
            if file_name.lower().endswith(".csv"):
                raw_data = zip_file.read(file_name)
                encoding = chardet.detect(raw_data)["encoding"]

                if not raw_data.strip():
                    logging.warning("CSV vazio no anexo ZIP: %s", file_name)
                    continue

                try:
                    decoded_data = raw_data.decode(encoding or "utf-8", errors="replace")
                    if not decoded_data.strip():
                        logging.warning("CSV vazio no anexo ZIP: %s", file_name)
                        continue
                    return format_csv(decoded_data, column_mapping, skiprows)
                except EmptyDataError:
                    logging.warning(
                        "CSV sem colunas apos skiprows=%s no arquivo: %s",
                        skiprows,
                        file_name,
                    )
                    continue
    return None


def fetch_email_with_zip(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: Optional[str],
    target_date: Optional[date] = None,
    subject_suffix: Optional[str] = None,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[bytes]:
    """Busca e-mails (data unica, intervalo ou dia atual) e retorna os ZIPs.

    Os anexos vem ordenados cronologicamente, do mais antigo para o mais
    recente. Sem start_date/end_date/target_date, mantem o comportamento
    legado de buscar apenas o dia atual.
    """
    return _fetch_sorted_attachments(
        imap_server,
        email,
        password,
        sender_email,
        extension=".zip",
        subject=subject,
        subject_suffix=subject_suffix,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
    )


def fetch_email_with_csv(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: str,
    target_date: Optional[date] = None,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[bytes]:
    """Busca e-mails (data unica, intervalo ou dia atual) e retorna os CSVs.

    Os anexos vem ordenados cronologicamente, do mais antigo para o mais
    recente. Sem start_date/end_date/target_date, mantem o comportamento
    legado de buscar apenas o dia atual.
    """
    return _fetch_sorted_attachments(
        imap_server,
        email,
        password,
        sender_email,
        extension=".csv",
        subject=subject,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
    )


def extract_csv_from_payload(
    payload: bytes, column_mapping: dict, skiprows: int = 0
) -> Optional[pd.DataFrame]:
    """Decodifica payload CSV e aplica formatação padrão."""
    if not payload.strip():
        logging.warning("Anexo CSV vazio.")
        return None

    encoding = chardet.detect(payload)["encoding"]
    decoded_data = payload.decode(encoding or "utf-8", errors="replace")
    if not decoded_data.strip():
        logging.warning("Anexo CSV vazio apos decodificacao.")
        return None

    try:
        return format_csv(decoded_data, column_mapping, skiprows)
    except EmptyDataError:
        logging.warning("CSV sem colunas apos skiprows=%s.", skiprows)
        return None


def fetch_and_process_email(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: str,
    column_mapping: dict,
    skiprows: int = 0,
    target_date: Optional[date] = None,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Optional[str]:
    """Busca e processa e-mails (data unica, intervalo ou dia atual), extraindo CSVs."""
    try:
        zip_payloads = fetch_email_with_zip(
            imap_server,
            email,
            password,
            sender_email,
            subject,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
        )
        if not zip_payloads:
            logging.warning("Nenhum anexo ZIP encontrado.")
            return None

        logging.info("Total de anexos ZIP encontrados: %s", len(zip_payloads))

        dataframes: List[pd.DataFrame] = []
        for idx, zip_payload in enumerate(zip_payloads, start=1):
            csv_data = extract_csv_from_zip(zip_payload, column_mapping, skiprows)
            if csv_data is not None:
                dataframes.append(csv_data)
            else:
                logging.warning(
                    "ZIP %s ignorado por nao conter CSV valido.",
                    idx,
                )

        if dataframes:
            combined_df = pd.concat(dataframes, ignore_index=True)
            return combined_df.to_csv(index=False)

        logging.warning("Nenhum CSV processado.")
    except Exception as e:
        logging.error(f"Erro ao processar e-mails: {e}")
        raise


def fetch_and_process_email_csv_attachment(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: str,
    column_mapping: dict,
    skiprows: int = 0,
    target_date: Optional[date] = None,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Optional[str]:
    """Busca e processa e-mails (data unica, intervalo ou dia atual), CSV direto."""
    try:
        csv_payloads = fetch_email_with_csv(
            imap_server,
            email,
            password,
            sender_email,
            subject,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
        )
        if not csv_payloads:
            logging.warning("Nenhum anexo CSV encontrado.")
            return None

        logging.info("Total de anexos CSV encontrados: %s", len(csv_payloads))

        dataframes: List[pd.DataFrame] = []
        for idx, payload in enumerate(csv_payloads, start=1):
            csv_data = extract_csv_from_payload(payload, column_mapping, skiprows)
            if csv_data is not None:
                dataframes.append(csv_data)
            else:
                logging.warning(
                    "CSV %s ignorado por nao conter dados validos.",
                    idx,
                )

        if dataframes:
            combined_df = pd.concat(dataframes, ignore_index=True)
            return combined_df.to_csv(index=False)

        logging.warning("Nenhum CSV processado.")
        return None
    except Exception as e:
        logging.error(f"Erro ao processar e-mails com CSV direto: {e}")
        raise
