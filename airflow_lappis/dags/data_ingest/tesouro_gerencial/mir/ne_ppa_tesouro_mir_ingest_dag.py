import csv
import json
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Tuple

import chardet
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from cliente_email import fetch_email_with_zip, resolve_email_date_range
from email_ingest_params import date_range_params
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

default_args = {
    "owner": "Ingrid",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

TABLE_SCHEMA = "siafi"
TABLE_NAME = "ne_tesouro_ppa"
EMAIL_SUBJECT = "notas_empenho_ppa_mir"

# Colunas fixas (posicoes 0-31), sempre presentes, mapeadas por posicao. A
# posicao 31 e o marcador do pivot ("Item Informacao Codigo") no cabecalho,
# mas nos dados carrega o "Grupo Despesa Nome".
FIXED_COLUMNS: List[str] = [
    "programa_governo",  # 0
    "programa_governo_descricao",  # 1
    "acao_governo",  # 2
    "acao_governo_descricao",  # 3
    "emissao_mes",  # 4
    "emissao_dia",  # 5
    "ne_ccor",  # 6
    "ug_responsavel_codigo",  # 7  UG Responsavel Codigo
    "ug_responsavel_nome",  # 8  UG Responsavel Nome
    "ne_num_processo",  # 9
    "ne_info_complementar",  # 10
    "ne_ccor_descricao",  # 11
    "doc_observacao",  # 12
    "natureza_despesa",  # 13
    "natureza_despesa_descricao",  # 14
    "ne_ccor_favorecido",  # 15
    "ne_ccor_favorecido_descricao",  # 16
    "ne_ccor_ano_emissao",  # 17
    "ptres",  # 18
    "fonte_recursos_detalhada",  # 19
    "fonte_recursos_detalhada_descricao",  # 20
    "plano_orcamentario_codigo_uo",  # 21 Plano Orcamentario Codigo UO
    "plano_orcamentario_codigo_funcao",  # 22 Plano Orcamentario Codigo Funcao
    "plano_orcamentario_codigo_subfuncao",  # 23 Plano Orcamentario Codigo Subfuncao
    "plano_orcamentario_codigo_programa",  # 24 Plano Orcamentario Codigo Programa
    "plano_orcamentario_codigo_acao",  # 25 Plano Orcamentario Codigo Acao
    "plano_orcamentario_codigo_po",  # 26
    "plano_orcamentario_nome",  # 27
    "resultado_eof_codigo",  # 28
    "resultado_eof_nome",  # 29
    "grupo_despesa",  # 30
    "grupo_despesa_desc",  # 31
]
FIXED_WIDTH = len(FIXED_COLUMNS)

# Colunas financeiras (posicoes 32+), pivotadas pelo Tesouro (uma por "Item
# Informacao"). Sao mapeadas por CODIGO, nao por posicao: o Tesouro so emite a
# coluna de um item quando ha valor para ele no periodo, entao qualquer uma
# pode faltar (ex.: sem "restos a pagar pagos" o cabecalho vem com 37 colunas
# em vez de 38). A ausente vira None no registro.
FINANCIAL_COLUMNS_BY_CODE: Dict[str, str] = {
    "13": "dotacao_atualizada",
    "29": "despesas_empenhadas",
    "31": "despesas_liquidadas",
    "34": "despesas_pagas",
    "50": "restos_a_pagar_inscritos",
    "52": "restos_a_pagar_pagos",
}

# Ancora na ultima posicao fixa (31) para detectar desalinhamento da parte fixa.
ITEM_INFO_HEADER = "Item Informação Código"

# Schema canonico completo. Todo registro sai com todas essas chaves (None nas
# financeiras ausentes) para ficar homogeneo: insert_data deriva as colunas do
# primeiro registro (flattened_data[0].keys()), entao um registro com menos
# chaves gravaria colunas desalinhadas ou perderia valores.
TARGET_COLUMNS: List[str] = FIXED_COLUMNS + list(FINANCIAL_COLUMNS_BY_CODE.values())

HEADER_MARKER = '"Programa Governo Código"'
SUB_HEADER_LINES = 2

# O relatorio mistura dois graos (mesmo problema do ne_tesouro_emendas):
#   - Empenho: uma linha por movimentacao contabil de uma NE real
#     (ne_ccor != '-9').
#   - Dotacao: orcamento no grao da classificacao orcamentaria, sem
#     empenho associado — ne_ccor = '-9' em todas as linhas, e um mesmo
#     ne_ccor real ainda pode repetir em varias linhas (uma por
#     favorecido/valor). Por isso a chave inclui a classificacao
#     orcamentaria e os proprios valores financeiros, que sao o que
#     de fato distingue linhas de uma mesma NE ou dotacao.
UNIQUE_KEY = [
    "ne_ccor",
    "natureza_despesa",
    "doc_observacao",
    "ne_ccor_ano_emissao",
    "emissao_dia",
    "emissao_mes",
    "ne_ccor_favorecido",
    "fonte_recursos_detalhada",
    "ptres",
    "plano_orcamentario_codigo_po",
    "grupo_despesa",
    "dotacao_atualizada",
    "despesas_empenhadas",
    "despesas_liquidadas",
    "despesas_pagas",
    "restos_a_pagar_inscritos",
    "restos_a_pagar_pagos",
]


def _decode_csv(raw_data: bytes) -> str:
    encoding = chardet.detect(raw_data)["encoding"] or "utf-8"
    return raw_data.decode(encoding, errors="replace")


def _build_positional_columns(header_row: List[str]) -> List[str]:
    """Monta o mapa posicao -> coluna alvo a partir do cabecalho do relatorio.

    As 32 colunas fixas vem por posicao; as financeiras (a partir de
    FIXED_WIDTH) sao resolvidas pelo codigo "Item Informacao" na propria linha
    de cabecalho, pois qualquer uma pode faltar quando nao ha dado no periodo.
    Levanta ValueError se a parte fixa desalinhou ou se surgir um codigo
    financeiro desconhecido/duplicado.
    """
    # Sem a ancora no lugar, mapear por posicao gravaria colunas desalinhadas.
    anchor = header_row[FIXED_WIDTH - 1] if len(header_row) >= FIXED_WIDTH else None
    if anchor != ITEM_INFO_HEADER:
        raise ValueError(
            f"Layout do relatorio mudou: esperava {FIXED_WIDTH} colunas fixas "
            f"terminando em '{ITEM_INFO_HEADER}' na posicao {FIXED_WIDTH - 1}, "
            f"mas o cabecalho tem {len(header_row)} colunas e a posicao "
            f"{FIXED_WIDTH - 1} e '{anchor}'. Revise FIXED_COLUMNS antes de "
            "prosseguir."
        )

    financial_positions: List[str] = []
    seen_codes: set = set()
    for offset, code in enumerate(header_row[FIXED_WIDTH:]):
        target = FINANCIAL_COLUMNS_BY_CODE.get(code)
        if target is None:
            raise ValueError(
                f"Layout do relatorio mudou: coluna financeira desconhecida na "
                f"posicao {FIXED_WIDTH + offset} com codigo Item Informacao "
                f"'{code}'. Codigos conhecidos: "
                f"{sorted(FINANCIAL_COLUMNS_BY_CODE)}."
            )
        if code in seen_codes:
            raise ValueError(
                f"Layout do relatorio mudou: codigo Item Informacao '{code}' "
                "aparece duplicado no cabecalho."
            )
        seen_codes.add(code)
        financial_positions.append(target)

    missing = [c for c in FINANCIAL_COLUMNS_BY_CODE if c not in seen_codes]
    if missing:
        logging.info(
            "Parser: colunas financeiras ausentes neste relatorio (sem dado no "
            "periodo): %s.",
            ", ".join(f"{c}->{FINANCIAL_COLUMNS_BY_CODE[c]}" for c in missing),
        )

    return FIXED_COLUMNS + financial_positions


def parse_ppa_csv(csv_data: str) -> List[Dict[str, Any]]:
    """Parser do relatorio "Notas de empenhos por programa PPA" do Tesouro.

    Le sempre como texto (sem passar por pandas.read_csv, que inferiria
    tipos numericos e comeria os zeros a esquerda de codigos como
    programa_governo "0032"). Mapeia as 32 colunas fixas por posicao e as
    financeiras por codigo "Item Informacao" (qualquer uma pode faltar no
    relatorio), ignora a linha final "Total" e linhas cuja largura nao bate
    com o cabecalho.
    """
    lines = csv_data.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.lstrip().startswith(HEADER_MARKER)),
        None,
    )
    if header_idx is None:
        raise ValueError(
            f"Cabecalho do relatorio nao encontrado — esperava uma linha "
            f"comecando com {HEADER_MARKER}."
        )

    header_row = next(csv.reader([lines[header_idx]]))
    positional_columns = _build_positional_columns(header_row)
    expected_width = len(positional_columns)

    data_start = header_idx + 1 + SUB_HEADER_LINES
    records: List[Dict[str, Any]] = []
    skipped = 0
    for line in lines[data_start:]:
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            skipped += 1
            continue
        if row and row[0] == "Total":
            continue
        if len(row) != expected_width:
            skipped += 1
            continue

        # Comeca com o schema canonico completo: financeiras ausentes ficam
        # None, mantendo todos os registros com as mesmas chaves.
        record: Dict[str, Any] = {name: None for name in TARGET_COLUMNS}
        for pos, name in enumerate(positional_columns):
            record[name] = row[pos].strip() or None
        records.append(record)

    if skipped:
        logging.warning(
            "Parser: %s linha(s) descartada(s) por largura invalida.", skipped
        )
    logging.info("Parser concluido: %s linhas no schema canonico.", len(records))
    return records


def _filter_and_dedupe(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Mantem os dois graos: empenho (ne_ccor real) e dotacao
    # (ne_ccor = '-9', so dotacao_atualizada preenchida). Um filtro so por
    # ano em ne_ccor_ano_emissao descartaria toda a dotacao, que traz '-9'
    # nesse campo tambem.
    kept = [
        r
        for r in records
        if (r.get("ne_ccor_ano_emissao") or "").startswith("20")
        or r.get("dotacao_atualizada") is not None
    ]

    # Protege o ON CONFLICT (execute_values) contra chaves repetidas no
    # mesmo lote, que fariam o INSERT inteiro falhar.
    seen: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for r in kept:
        key = tuple(r.get(c) for c in UNIQUE_KEY)
        seen[key] = r
    return list(seen.values())


def _reset_table_if_has_primary_key(db: ClientPostgresDB) -> None:
    """Dropa a tabela se ela tiver uma PRIMARY KEY.

    insert_data() e chamado so com conflict_fields=UNIQUE_KEY (sem
    primary_key): o ON CONFLICT usa o UNIQUE INDEX criado a partir de
    conflict_fields, que aceita nulos. Uma PRIMARY KEY, por outro lado,
    torna todas as colunas da chave NOT NULL — e como a chave inclui as
    6 colunas financeiras (normalmente so uma vem preenchida por linha),
    isso quebra o insert com NotNullViolation. Se uma execucao anterior
    (ou uma tabela criada manualmente) deixou uma PRIMARY KEY, dropamos
    para recriar sem ela. Seguro: cada e-mail traz o relatorio completo,
    entao a proxima carga repopula tudo.
    """
    rows = db.execute_query(
        f"SELECT 1 FROM information_schema.table_constraints "
        f"WHERE table_schema = '{TABLE_SCHEMA}' AND table_name = '{TABLE_NAME}' "
        f"AND constraint_type = 'PRIMARY KEY' LIMIT 1;"
    )
    if not rows:
        return

    logging.warning(
        "PRIMARY KEY indevida detectada em %s.%s — dropando para recriar sem PK.",
        TABLE_SCHEMA,
        TABLE_NAME,
    )
    db.execute_non_query(f"DROP TABLE IF EXISTS {TABLE_SCHEMA}.{TABLE_NAME} CASCADE;")


with DAG(
    dag_id="email_tesouro_ppa_ingest_dag",
    default_args=default_args,
    description=(
        "Processa o anexo de notas de empenho por programa PPA vindo do "
        "email, formata e insere no db"
    ),
    schedule_interval=get_dynamic_schedule(
        "empenhos_tesouro_ppa_ingest_dag", default="5 0 * * *"
    ),
    start_date=datetime(2023, 12, 1),
    catchup=False,
    params=date_range_params(),
    tags=["MIR", "email", "empenhos", "tesouro", "ppa"],
) as dag:

    def _get_db_client() -> ClientPostgresDB:
        return ClientPostgresDB(get_postgres_conn("postgres_mir"))

    def _insert_records(records: List[Dict[str, Any]], db: ClientPostgresDB) -> int:
        data = _filter_and_dedupe(records)
        for record in data:
            record["dt_ingest"] = datetime.now().isoformat()

        _reset_table_if_has_primary_key(db)

        db.insert_data(
            data,
            TABLE_NAME,
            conflict_fields=UNIQUE_KEY,
            schema=TABLE_SCHEMA,
        )
        return len(data)

    def fetch_and_ingest(**context: Dict[str, Any]) -> Dict[str, int]:
        """Processa cada anexo e ingere imediatamente, evitando acumulo em memoria."""
        creds = json.loads(Variable.get("email_credentials"))
        params = context.get("params", {})
        start_date, end_date = resolve_email_date_range(
            params.get("data_inicial"), params.get("data_final")
        )

        zip_payloads: List[bytes] = fetch_email_with_zip(
            creds["imap_server"],
            creds["email"],
            creds["password"],
            creds["sender_email"],
            None,
            subject_suffix=EMAIL_SUBJECT,
            start_date=start_date,
            end_date=end_date,
        )

        if not zip_payloads:
            logging.warning("Nenhum anexo ZIP encontrado.")
            return {"attachments": 0, "records": 0}

        logging.info("Total de anexos ZIP encontrados: %s", len(zip_payloads))

        db = _get_db_client()
        total_records = 0

        for idx, payload in enumerate(zip_payloads, 1):
            with zipfile.ZipFile(BytesIO(payload)) as zip_file:
                csv_names = [n for n in zip_file.namelist() if n.lower().endswith(".csv")]
                if not csv_names:
                    logging.warning("Anexo %s ignorado (sem CSV no ZIP).", idx)
                    continue
                raw_data = zip_file.read(csv_names[0])

            if not raw_data.strip():
                logging.warning("Anexo %s ignorado (CSV vazio).", idx)
                continue

            csv_data = _decode_csv(raw_data)
            records = parse_ppa_csv(csv_data)
            count = _insert_records(records, db)
            total_records += count
            logging.info("Anexo %s: %s registros inseridos", idx, count)
            del records

        logging.info("Total: %s anexos, %s registros", len(zip_payloads), total_records)
        return {"attachments": len(zip_payloads), "records": total_records}

    PythonOperator(
        task_id="fetch_and_ingest",
        python_callable=fetch_and_ingest,
    )
