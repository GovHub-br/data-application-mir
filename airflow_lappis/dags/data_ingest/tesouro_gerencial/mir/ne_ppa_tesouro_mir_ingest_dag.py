import csv
import json
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

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

# O relatorio "Notas de empenhos por programa PPA" traz 38 colunas, todas
# mapeadas por posicao no schema alvo. Colunas descartadas ficam como None,
# mas hoje nao ha nenhuma — se mapearmos so as que interessam sem preencher
# as posicoes intermediarias, elas entram desalinhadas.
#
# As posicoes 32-37 sao os valores financeiros ja pivotados em colunas pelo
# proprio Tesouro (uma coluna por "Item Informacao": 13, 29, 31, 34, 50, 52).
# O cabecalho do relatorio tem 3 linhas empilhadas por causa desse pivot; o
# nome real de cada coluna financeira vem da 2a linha (codigo -> descricao),
# nao da 1a.
POSITIONAL_COLUMNS: List[Optional[str]] = [
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
    "dotacao_atualizada",  # 32  Item Informacao 13
    "despesas_empenhadas",  # 33  Item Informacao 29
    "despesas_liquidadas",  # 34  Item Informacao 31
    "despesas_pagas",  # 35  Item Informacao 34
    "restos_a_pagar_inscritos",  # 36  Item Informacao 50
    "restos_a_pagar_pagos",  # 37  Item Informacao 52
]
EXPECTED_WIDTH = len(POSITIONAL_COLUMNS)
EXPECTED_ITEM_CODES = {32: "13", 33: "29", 34: "31", 35: "34", 36: "50", 37: "52"}

TARGET_COLUMNS: List[str] = [c for c in POSITIONAL_COLUMNS if c is not None]

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


def parse_ppa_csv(csv_data: str) -> List[Dict[str, Any]]:
    """Parser do relatorio "Notas de empenhos por programa PPA" do Tesouro.

    Le sempre como texto (sem passar por pandas.read_csv, que inferiria
    tipos numericos e comeria os zeros a esquerda de codigos como
    programa_governo "0032"). Mapeia as 38 colunas por posicao, descarta
    as 7 que nao fazem parte do schema alvo, ignora a linha final "Total"
    e linhas cuja largura nao bate com o cabecalho.
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
    if len(header_row) != EXPECTED_WIDTH:
        raise ValueError(
            f"Layout do relatorio mudou: cabecalho tem {len(header_row)} "
            f"colunas, esperava {EXPECTED_WIDTH}. Revise POSITIONAL_COLUMNS "
            "antes de prosseguir — mapear posicoes erradas grava colunas "
            "desalinhadas em silencio."
        )

    # Os codigos "Item Informacao" (13/29/31/34/50/52) ficam na propria
    # linha de cabecalho, nao na sub-linha seguinte (que traz os nomes
    # descritivos, ex.: "DOTACAO ATUALIZADA").
    for pos, expected_code in EXPECTED_ITEM_CODES.items():
        actual = header_row[pos] if pos < len(header_row) else None
        if actual != expected_code:
            raise ValueError(
                f"Layout do relatorio mudou: coluna financeira na posicao "
                f"{pos} tem codigo Item Informacao '{actual}', esperava "
                f"'{expected_code}' ({POSITIONAL_COLUMNS[pos]})."
            )

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
        if len(row) != EXPECTED_WIDTH:
            skipped += 1
            continue

        record = {
            name: (row[pos].strip() or None)
            for pos, name in enumerate(POSITIONAL_COLUMNS)
            if name is not None
        }
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
    schedule_interval=get_dynamic_schedule("empenhos_tesouro_ppa_ingest_dag"),
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
