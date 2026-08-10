from typing import Any, Dict, List, Optional
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.models.param import Param
from datetime import datetime, timedelta
import csv
import io
import json
import logging
import cliente_email
from schedule_loader import get_dynamic_schedule
from cliente_email import fetch_and_process_email
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn
import pandas as pd

default_args = {
    "owner": "Tiago",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

TABLE_SCHEMA = "siafi"
TABLE_NAME = "ne_tesouro_emendas"
EMAIL_SUBJECT = "notas_de_empenhos_emendas_parlamentares"

TARGET_COLUMNS: List[str] = [
    "emissao_mes",
    "emissao_dia",
    "programa_governo",
    "programa_governo_descricao",
    "acao_governo",
    "acao_governo_descricao",
    "autor_emendas_orcamento",
    "autor_emendas_orcamento_descricao",
    "localizador_gasto",
    "localizador_gasto_descricao",
    "regiao_pt",
    "uf_pt",
    "uf_pt_descricao",
    "municipio_pt",
    "ne_ccor",
    "ne_num_processo",
    "ne_info_complementar",
    "ne_ccor_descricao",
    "doc_observacao",
    "grupo_despesa",
    "grupo_despesa_descricao",
    "natureza_despesa",
    "natureza_despesa_descricao",
    "modalidade_aplicacao",
    "modalidade_aplicacao_descricao",
    "ne_ccor_favorecido",
    "ne_ccor_favorecido_descricao",
    "ne_ccor_ano_emissao",
    "ptres",
    "fonte_recursos_detalhada",
    "fonte_recursos_detalhada_descricao",
    "dotacao_inicial",
    "dotacao_atualizada",
    "despesas_empenhadas",
    "despesas_liquidadas",
    "despesas_pagas",
    "restos_a_pagar_inscritos",
    "restos_a_pagar_pagos",
]

HEADER_TO_CANONICAL: Dict[str, str] = {
    "Emissão - Mês": "emissao_mes",
    "Emissão - Dia": "emissao_dia",
    "Programa Governo": "programa_governo",
    "Ação Governo": "acao_governo",
    "Autor Emendas Orçamento": "autor_emendas_orcamento",
    "Localizador Gasto": "localizador_gasto",
    "Região PT": "regiao_pt",
    "UF PT": "uf_pt",
    "Município PT": "municipio_pt",
    "NE CCor": "ne_ccor",
    "NE - Núm. Processo": "ne_num_processo",
    "NE - Informação Complementar": "ne_info_complementar",
    "NE CCor - Descrição": "ne_ccor_descricao",
    "Doc - Observação": "doc_observacao",
    "Grupo Despesa": "grupo_despesa",
    "Natureza Despesa": "natureza_despesa",
    "Modalidade Aplicação": "modalidade_aplicacao",
    "NE CCor - Favorecido": "ne_ccor_favorecido",
    "NE CCor - Ano Emissão": "ne_ccor_ano_emissao",
    "PTRES": "ptres",
    # Header diz "Item Informação" mas a coluna traz o codigo da fonte de
    # recursos (ex.: 1000000000 = RECURSOS LIVRES DA UNIAO).
    "Item Informação": "fonte_recursos_detalhada",
}

HEADERS_WITH_DESCRICAO = {
    "Programa Governo",
    "Ação Governo",
    "Autor Emendas Orçamento",
    "Localizador Gasto",
    "UF PT",
    "Grupo Despesa",
    "Natureza Despesa",
    "Modalidade Aplicação",
    "NE CCor - Favorecido",
    "Item Informação",
}

ITEM_CODE_TO_CANONICAL = {
    "9": "dotacao_inicial",
    "13": "dotacao_atualizada",
    "29": "despesas_empenhadas",
    "31": "despesas_liquidadas",
    "34": "despesas_pagas",
    "50": "restos_a_pagar_inscritos",
    "52": "restos_a_pagar_pagos",
}

HEADER_MARKER = '"Emissão - Mês"'
SUB_HEADER_LINES = 2

# Coluna do schema antigo (posicional, quebrado) usada para detectar
# tabelas que precisam ser recriadas. Ver reset_table_if_legacy_schema.
LEGACY_SCHEMA_MARKER_COLUMN = "item_informacao"

# O relatorio agora traz DOIS graos na mesma tabela:
#   - Empenho: cada linha e uma movimentacao contabil de uma NE
#     (ne_ccor real, ne_ccor_ano_emissao com o ano).
#   - Dotacao (itens 9/13): orcamento no grao da classificacao
#     (programa/acao/localizador/natureza/modalidade/fonte/ptres),
#     sem empenho — ne_ccor = '-9' em todas as linhas.
# Como ne_ccor e constante ('-9') nas linhas de dotacao, a chave precisa
# incluir a classificacao orcamentaria para identifica-las sem colisao;
# para as linhas de empenho essas colunas sao funcao do proprio empenho,
# entao nao alteram a deduplicacao.
UNIQUE_KEY = [
    "ne_ccor",
    "emissao_mes",
    "emissao_dia",
    "doc_observacao",
    "ptres",
    "natureza_despesa",
    "modalidade_aplicacao",
    "localizador_gasto",
    "fonte_recursos_detalhada",
]


def _build_column_map(header_row: List[str]) -> Dict[str, int]:
    col_map: Dict[str, int] = {}
    for pos, raw in enumerate(header_row):
        name = raw.strip()
        if name in HEADER_TO_CANONICAL:
            canonical = HEADER_TO_CANONICAL[name]
            col_map[canonical] = pos
            if name in HEADERS_WITH_DESCRICAO:
                col_map[f"{canonical}_descricao"] = pos + 1
        elif name in ITEM_CODE_TO_CANONICAL:
            col_map[ITEM_CODE_TO_CANONICAL[name]] = pos
    return col_map


def parse_tesouro_emendas_csv(
    csv_data: str,
    column_mapping: Optional[Dict[int, str]] = None,
    skiprows: int = 0,
) -> pd.DataFrame:
    """Parser do relatorio do Tesouro Gerencial de empenhos de emendas.

    O arquivo concatena multiplos sub-relatorios (um por "Ano Lançamento"),
    cada um com seu proprio cabecalho e numero de colunas financeiras
    diferente. O parser detecta cada sub-relatorio pelo cabecalho
    repetido e mapeia colunas pelo nome (nao por posicao).

    `column_mapping` e `skiprows` sao ignorados — existem so para manter
    a assinatura de cliente_email.format_csv, que esta funcao substitui
    via monkey-patch.
    """
    del column_mapping, skiprows

    lines = csv_data.splitlines()
    header_indices = [
        i for i, line in enumerate(lines) if line.lstrip().startswith(HEADER_MARKER)
    ]
    if not header_indices:
        raise ValueError(
            "Nenhum cabecalho de empenhos de emendas encontrado no CSV — "
            f"esperava linhas comecando com {HEADER_MARKER}."
        )

    sub_report_ranges = [
        (start, header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines))
        for idx, start in enumerate(header_indices)
    ]

    records: List[Dict[str, Any]] = []
    for sub_idx, (h_start, h_end) in enumerate(sub_report_ranges, start=1):
        header_row = next(csv.reader([lines[h_start]]))
        col_map = _build_column_map(header_row)
        expected_width = len(header_row)
        data_start = h_start + 1 + SUB_HEADER_LINES

        ne_pos = col_map.get("ne_ccor")
        if ne_pos is None:
            logging.warning(
                "Sub-relatorio %s: cabecalho sem coluna 'NE CCor'; ignorando.",
                sub_idx,
            )
            continue

        financial_present = sorted(
            c for c in col_map if c in ITEM_CODE_TO_CANONICAL.values()
        )
        kept = 0
        for line in lines[data_start:h_end]:
            if not line.strip():
                continue
            try:
                row = next(csv.reader([line]))
            except csv.Error:
                continue
            if len(row) != expected_width:
                continue
            if ne_pos >= len(row) or not row[ne_pos].strip():
                continue

            record: Dict[str, Any] = {}
            for canonical, pos in col_map.items():
                if pos < len(row):
                    value = row[pos].strip()
                    record[canonical] = value if value else None
            records.append(record)
            kept += 1

        logging.info(
            "Sub-relatorio %s: %s colunas, %s linhas, financeiras: %s",
            sub_idx,
            expected_width,
            kept,
            ", ".join(financial_present) or "(nenhuma)",
        )

    df = pd.DataFrame(records, columns=TARGET_COLUMNS)
    logging.info("Parser concluido: %s linhas no schema canonico.", len(df))
    return df


def reset_table_if_legacy_schema(db: ClientPostgresDB) -> None:
    """Dropa a tabela se ainda estiver no schema antigo.

    O schema antigo lia colunas por posicao fixa e gravava valores de
    Restos a Pagar como despesas_liquidadas/pagas em sub-relatorios de
    34 colunas. Os dados existentes estao semanticamente corrompidos —
    recarregar do zero e a unica correcao segura.
    """
    rows = db.execute_query(
        f"SELECT 1 FROM information_schema.columns "
        f"WHERE table_schema = '{TABLE_SCHEMA}' "
        f"AND table_name = '{TABLE_NAME}' "
        f"AND column_name = '{LEGACY_SCHEMA_MARKER_COLUMN}' LIMIT 1;"
    )
    if not rows:
        return

    logging.warning(
        "Schema antigo detectado em %s.%s — dropando para recriar limpo.",
        TABLE_SCHEMA,
        TABLE_NAME,
    )
    db.execute_non_query(f"DROP TABLE IF EXISTS {TABLE_SCHEMA}.{TABLE_NAME} CASCADE;")


def reset_table_if_pk_mismatch(db: ClientPostgresDB) -> None:
    """Dropa a tabela se a PRIMARY KEY nao corresponder a UNIQUE_KEY atual.

    A tabela antiga foi criada com PRIMARY KEY na chave de 4 colunas. A nova
    chave (empenho + dotacao) tem 9 colunas, e nao ha migracao automatica:
    - CREATE TABLE IF NOT EXISTS nao altera constraints de tabela existente;
    - ensure_unique_constraint nao ajuda porque o nome do indice, truncado em
      63 chars, colide com o da chave antiga (CREATE ... IF NOT EXISTS pula).
    Por isso comparamos a PK atual com a UNIQUE_KEY e, se diferir, recriamos a
    tabela — que passa a ter a PK composta correta. Seguro: cada e-mail traz o
    relatorio completo (Ano Lancamento >= 2022), entao a proxima carga repopula
    tudo. Idempotente: quando a PK ja bate, nao faz nada.
    """
    exists = db.execute_query(
        f"SELECT 1 FROM information_schema.tables "
        f"WHERE table_schema = '{TABLE_SCHEMA}' "
        f"AND table_name = '{TABLE_NAME}' LIMIT 1;"
    )
    if not exists:
        return

    pk_rows = db.execute_query(
        f"SELECT kcu.column_name "
        f"FROM information_schema.table_constraints tc "
        f"JOIN information_schema.key_column_usage kcu "
        f"  ON tc.constraint_name = kcu.constraint_name "
        f"  AND tc.table_schema = kcu.table_schema "
        f"WHERE tc.table_schema = '{TABLE_SCHEMA}' "
        f"  AND tc.table_name = '{TABLE_NAME}' "
        f"  AND tc.constraint_type = 'PRIMARY KEY';"
    )
    current_pk = {row[0] for row in pk_rows}
    if current_pk == set(UNIQUE_KEY):
        return

    logging.warning(
        "PK de %s.%s (%s) difere da UNIQUE_KEY (%s) — dropando para recriar.",
        TABLE_SCHEMA,
        TABLE_NAME,
        sorted(current_pk) or "nenhuma",
        sorted(UNIQUE_KEY),
    )
    db.execute_non_query(f"DROP TABLE IF EXISTS {TABLE_SCHEMA}.{TABLE_NAME} CASCADE;")


with DAG(
    dag_id="email_tesouro_emendas_ingest",
    default_args=default_args,
    description="Processa anexos dos empenhos vindo do email, formata e insere no db",
    schedule_interval=get_dynamic_schedule("empenhos_tesouro_emendas_ingest_dag"),
    start_date=datetime(2023, 12, 1),
    catchup=False,
    params={
        "data_referencia": Param(
            default=None,
            type=["string", "null"],
            title="Data de Referencia",
            description=(
                "Data para filtrar os e-mails recebidos (formato YYYY-MM-DD). "
                "Se nao informado, usa o dia atual."
            ),
        )
    },
    tags=["MIR", "email", "empenhos", "tesouro", "emendas"],
) as dag:

    def process_email_data(**context: Dict[str, Any]) -> Optional[Any]:
        creds = json.loads(Variable.get("email_credentials"))
        EMAIL = creds["email"]
        PASSWORD = creds["password"]
        IMAP_SERVER = creds["imap_server"]
        SENDER_EMAIL = creds["sender_email"]
        params = context.get("params", {})
        data_referencia = params.get("data_referencia")

        target_date = None
        if data_referencia:
            try:
                target_date = datetime.strptime(data_referencia, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError(
                    "Parametro 'data_referencia' invalido. Use o formato YYYY-MM-DD."
                ) from exc

        cliente_email.format_csv = parse_tesouro_emendas_csv

        try:
            logging.info(
                "Iniciando processamento dos emails para a data: %s",
                target_date.isoformat() if target_date else "dia atual",
            )
            csv_data = fetch_and_process_email(
                IMAP_SERVER,
                EMAIL,
                PASSWORD,
                SENDER_EMAIL,
                EMAIL_SUBJECT,
                column_mapping={},
                skiprows=0,
                target_date=target_date,
            )
            if not csv_data:
                logging.warning("Nenhum CSV valido foi extraido dos e-mails.")
                return None

            logging.info("CSV processado: %s caracteres.", len(csv_data))
            return csv_data
        except Exception as e:
            logging.error("Erro no processamento dos emails: %s", str(e))
            raise

    def insert_data_to_db(**context: Dict[str, Any]) -> None:
        try:
            task_instance: Any = context["ti"]
            csv_data: Any = task_instance.xcom_pull(task_ids="process_emails")

            if not csv_data:
                logging.warning("Nenhum dado para inserir no banco.")
                return

            df = pd.read_csv(io.StringIO(csv_data), dtype=str, keep_default_na=False)
            df = df.replace({"": None})
            # Mantem dois graos: empenhos (ne_ccor_ano_emissao com o ano) e
            # linhas de dotacao (itens 9/13, sem empenho). O filtro antigo
            # (so ano) descartava toda a dotacao.
            is_empenho = df["ne_ccor_ano_emissao"].fillna("").str.startswith("20")
            has_dotacao = df["dotacao_inicial"].notna() | df["dotacao_atualizada"].notna()
            df = df[is_empenho | has_dotacao]

            # Protege o ON CONFLICT (execute_values) contra chaves repetidas no
            # mesmo lote, que fariam o INSERT inteiro falhar.
            df = df.drop_duplicates(subset=UNIQUE_KEY, keep="last")

            data = df.where(pd.notnull(df), None).to_dict(orient="records")
            for record in data:
                record["dt_ingest"] = datetime.now().isoformat()

            postgres_conn_str = get_postgres_conn("postgres_mir")
            db = ClientPostgresDB(postgres_conn_str)

            reset_table_if_legacy_schema(db)
            reset_table_if_pk_mismatch(db)

            db.insert_data(
                data,
                TABLE_NAME,
                conflict_fields=UNIQUE_KEY,
                primary_key=UNIQUE_KEY,
                schema=TABLE_SCHEMA,
            )
            logging.info(
                "Inseridos %s registros em %s.%s.",
                len(data),
                TABLE_SCHEMA,
                TABLE_NAME,
            )
        except Exception as e:
            logging.error("Erro ao inserir dados no banco: %s", str(e))
            raise

    process_emails_task = PythonOperator(
        task_id="process_emails",
        python_callable=process_email_data,
        provide_context=True,
    )

    insert_to_db_task = PythonOperator(
        task_id="insert_to_db",
        python_callable=insert_data_to_db,
        provide_context=True,
    )

    process_emails_task >> insert_to_db_task
