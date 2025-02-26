import logging
import io
import zipfile
from typing import Optional
from typing_extensions import Buffer
import pandas as pd
from imap_tools import MailBox, AND, MailMessage
import chardet
import pytz
from datetime import datetime

# Configuração do log
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def format_csv(csv_data: str, column_mapping: dict) -> pd.DataFrame:
    """Formata um arquivo CSV conforme mapeamento de colunas."""
    try:
        logging.info("Formatando CSV na memória...")
        df = pd.read_csv(io.StringIO(csv_data), skiprows=5, header=None)
        df.columns = pd.Index(
            [column_mapping.get(i, f"col_{i}") for i in range(len(df.columns))]
        )
        logging.info("CSV formatado com sucesso.")
        return df
    except Exception as e:
        logging.error("Erro ao formatar CSV.")
        raise ValueError(f"Erro ao formatar CSV: {e}")


def extract_csv_from_zip(
    zip_payload: Buffer, column_mapping: dict
) -> Optional[pd.DataFrame]:
    """Extrai e formata arquivos CSV de um arquivo ZIP."""
    try:
        logging.info("Abrindo arquivo ZIP...")
        with zipfile.ZipFile(io.BytesIO(zip_payload)) as zip_file:
            for file_name in zip_file.namelist():
                if file_name.endswith(".csv"):
                    logging.info(f"Processando arquivo CSV: {file_name}")
                    with zip_file.open(file_name) as csv_file:
                        raw_data = csv_file.read()
                        encoding = chardet.detect(raw_data)["encoding"]
                        logging.info(f"Codificação detectada: {encoding}")
                        decoded_data = raw_data.decode(encoding)
                        return format_csv(decoded_data, column_mapping)
        logging.warning("Nenhum arquivo CSV encontrado no ZIP.")
        return None
    except Exception as e:
        logging.error("Erro ao processar arquivo ZIP.")
        raise ValueError(f"Erro ao extrair CSV do ZIP: {e}")


def fetch_emails(
    imap_server: str, email: str, password: str, sender_email: str, subject: str
) -> Optional[MailMessage]:
    """Busca e-mails no servidor IMAP conforme critérios especificados."""
    local_tz = pytz.timezone("America/Sao_Paulo")
    today = datetime.now(local_tz).date()
    logging.info(
        f"Conectando ao servidor IMAP para buscar e-mails de {sender_email} em {today}."
    )

    try:
        with MailBox(imap_server).login(email, password) as mailbox:
            emails: list[MailMessage] = list(
                mailbox.fetch(AND(date=today, from_=sender_email))
            )
            for email_item in emails:
                logging.info(f"E-mail encontrado: Assunto - '{email_item.subject}'")
                if email_item.subject == subject:
                    return email_item
        logging.warning("Nenhum e-mail com o assunto esperado encontrado.")
    except Exception as e:
        logging.error("Erro ao buscar e-mails.")
        raise ConnectionError(f"Erro ao buscar e-mails: {e}")
    return None


def process_email_attachments(
    email_item: MailMessage, column_mapping: dict
) -> Optional[pd.DataFrame]:
    """Processa os anexos ZIP de um e-mail e retorna o CSV formatado."""
    if not email_item:
        logging.warning("Nenhum e-mail válido fornecido para processamento.")
        return None

    for attachment in email_item.attachments:
        if attachment.filename.endswith(".zip"):
            logging.info(f"Anexo ZIP encontrado: {attachment.filename}. Processando...")
            return extract_csv_from_zip(attachment.payload, column_mapping)
        else:
            logging.info(f"Anexo ignorado: {attachment.filename} (não é ZIP).")

    logging.warning("Nenhum anexo ZIP encontrado no e-mail.")
    return None


def fetch_and_process_emails(
    email: str,
    password: str,
    imap_server: str,
    sender_email: str,
    subject: str,
    column_mapping: dict,
) -> Optional[str]:
    """Orquestra a busca de e-mails,
    processamento de anexos e retorno do CSV formatado."""
    try:
        email_item = fetch_emails(imap_server, email, password, sender_email, subject)
        csv_data = process_email_attachments(email_item, column_mapping)

        if csv_data is not None:
            logging.info("E-mail processado com sucesso. Retornando CSV formatado.")
            return csv_data.to_csv(index=False)
        else:
            logging.info("Nenhum CSV processado.")
            return None
    except Exception as e:
        logging.error("Erro durante o processamento de e-mails.")
        raise RuntimeError(f"Erro ao processar e-mails: {e}")
