from typing import Dict, Any, List
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import logging
import json
import re
import unicodedata
import pandas as pd
from schedule_loader import get_dynamic_schedule
from cliente_email import (
    fetch_email_with_zip,
    extract_csv_from_zip,
    open_mailbox,
    resolve_email_date_range,
)
from email_ingest_params import date_range_params
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn

default_args = {
    "owner": "Mateus",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

COLUMN_MAPPING = {
    0: "programa_governo",
    1: "programa_governo_descricao",
    2: "acao_governo",
    3: "acao_governo_descricao",
    4: "nc",
    5: "nc_transferencia", 
    6: "nc_fonte_recursos",
    7: "nc_fonte_recursos_descricao",
    8: "ptres",
    9: "nc_evento",
    10: "nc_evento_descricao",
    11: "nc_ug_responsavel",
    12: "nc_ug_responsavel_descricao",
    13: "nc_natureza_despesa",
    14: "nc_natureza_despesa_descricao",
    15: "nc_plano_interno",
    16: "nc_plano_interno_descricao1",
    17: "nc_plano_interno_descricao2",
    18: "favorecido_doc",
    19: "favorecido_doc_descricao",
    20: "favorecido_municipio",
    21: "favorecido_municipio_descricao",
    22: "nc_valor_linha",
    23: "movimento_liquido_moeda_origem",
}

# Configurações dos emails
EMAIL_CONFIGS = {
    "enviadas": {
        "subject": "notas_credito_mir_ate_2025",
        "column_mapping": COLUMN_MAPPING,
        "skiprows": 6,
    },
    "recebidas": {
        "subject": "notas_credito_recebidas_ate_2025",
        "column_mapping": None,
        "skiprows": 6,
    },
}
expected_columns = list(COLUMN_MAPPING.values())


def _sanitize_column_name(raw_name: str, fallback_index: int) -> str:
    """Normaliza um nome de coluna vindo de um cabecalho de CSV nao confiavel
    para um identificador SQL seguro: minusculo, sem acento/espaco/pontuacao,
    nao comecando com digito. create_table_if_not_exists nao faz esse
    saneamento sozinho (usa o nome direto no DDL), entao sem isso um
    cabecalho real tipo "Nº da NC" ou "Órgão Superior" quebraria a criacao
    da tabela de quarentena.
    """
    normalized = unicodedata.normalize("NFKD", str(raw_name))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]+", "_", ascii_only.strip().lower()).strip("_")
    if not name:
        return f"col_{fallback_index}"
    if name[0].isdigit():
        name = f"col_{name}"
    return name


with DAG(
    dag_id="email_notas_credito_ingest_mir_ate_2025",
    default_args=default_args,
    schedule_interval=get_dynamic_schedule(
        "email_notas_credito_ingest_mir_ate_2025", default="15 0 * * *"
    ),
    start_date=datetime(2023, 12, 1),
    catchup=False,
    params=date_range_params(),
    tags=["MIR", "SIAFI", "notas_credito"],
) as dag:

    def fetch_and_ingest(**context: Dict[str, Any]) -> Dict[str, int]:
        """
        Busca as NCs (enviadas e recebidas) e insere cada anexo imediatamente
        no banco, sem acumular todos os e-mails do intervalo em memória.

        As duas buscas reusam a MESMA sessão IMAP (open_mailbox) em vez de
        logar duas vezes — dois logins em sequência já foram o suficiente
        para estourar o [OVERQUOTA] do provedor.
        """
        creds = json.loads(Variable.get("email_credentials"))
        params = context.get("params", {})
        data_inicial, data_final = resolve_email_date_range(
            params.get("data_inicial"), params.get("data_final")
        )

        postgres_conn_str = get_postgres_conn("postgres_mir")
        db = ClientPostgresDB(postgres_conn_str)
        total_attachments = 0
        total_records = 0

        with open_mailbox(
            creds["imap_server"], creds["email"], creds["password"]
        ) as mailbox:
            for email_type, config in EMAIL_CONFIGS.items():
                logging.info(f"Iniciando o processamento das NCs {email_type}")
                zip_payloads: List[bytes] = fetch_email_with_zip(
                    creds["imap_server"],
                    creds["email"],
                    creds["password"],
                    creds["sender_email"],
                    config["subject"],
                    start_date=data_inicial,
                    end_date=data_final,
                    mailbox=mailbox,
                )

                if not zip_payloads:
                    logging.warning(f"Nenhum e-mail encontrado para NCs {email_type}")
                    continue

                logging.info(
                    "NCs %s: %s anexos encontrados", email_type, len(zip_payloads)
                )

                for idx, payload in enumerate(zip_payloads, 1):
                    df = extract_csv_from_zip(
                        payload, config["column_mapping"], config["skiprows"]
                    )
                    if df is None or df.empty:
                        logging.warning(
                            "NCs %s anexo %s ignorado (CSV inválido/vazio).",
                            email_type,
                            idx,
                        )
                        continue

                    # Se não tem mapeamento de colunas (recebidas), o CSV já
                    # foi lido com header=0 (nomes reais do relatório). NÃO
                    # sobrescrever esses nomes com expected_columns: o
                    # relatório de NCs recebidas tem o MIR como destinatário,
                    # não como emitente, e não há garantia de que suas
                    # colunas estejam na mesma ordem do relatório de
                    # enviadas — só bater a quantidade não é suficiente.
                    # Renomear por posição sem validar a identidade de cada
                    # coluna foi a causa de dados de 2023-2025 com colunas
                    # trocadas silenciosamente (ver investigação da issue
                    # #507). Até existir um column_mapping próprio para o
                    # layout real do relatório de recebidas, o anexo vai pra
                    # uma tabela de quarentena com os nomes de coluna REAIS
                    # do CSV (insert_data cria/altera a tabela sozinho a
                    # partir das chaves do dict) -- preserva o dado em vez de
                    # descartar, sem arriscar trocar coluna em
                    # nc_tesouro_pre_2026. Quando o mapeamento certo existir,
                    # dá pra migrar daqui pra lá.
                    if config["column_mapping"] is None:
                        if list(df.columns) != expected_columns:
                            logging.error(
                                "NCs %s anexo %s: cabecalho do CSV (%s) nao "
                                "corresponde ao layout esperado (%s). Dados "
                                "preservados em siafi.nc_tesouro_recebidas_raw "
                                "com as colunas originais -- NAO inseridos em "
                                "nc_tesouro_pre_2026 para nao trocar coluna.",
                                email_type,
                                idx,
                                list(df.columns),
                                expected_columns,
                            )
                            df_raw = df.copy()
                            df_raw.columns = pd.Index(
                                [
                                    _sanitize_column_name(col, i)
                                    for i, col in enumerate(df_raw.columns)
                                ]
                            )
                            raw_data = df_raw.to_dict(orient="records")
                            for record in raw_data:
                                record["dt_ingest"] = datetime.now().isoformat()
                                record["anexo_origem"] = f"{email_type}_{idx}"
                            db.insert_data(
                                raw_data, "nc_tesouro_recebidas_raw", schema="siafi"
                            )
                            total_attachments += 1
                            total_records += len(raw_data)
                            del raw_data
                            continue

                    data = df.to_dict(orient="records")
                    for record in data:
                        record["dt_ingest"] = datetime.now().isoformat()

                    db.insert_data(data, "nc_tesouro_pre_2026", schema="siafi")
                    total_attachments += 1
                    total_records += len(data)
                    logging.info(
                        "NCs %s anexo %s: %s registros inseridos",
                        email_type,
                        idx,
                        len(data),
                    )
                    del df, data

        logging.info("Total: %s anexos, %s registros", total_attachments, total_records)
        return {"attachments": total_attachments, "records": total_records}

    def clean_duplicates(**context: Dict[str, Any]) -> None:
        """
        Task para remover duplicados da tabela 'siafi.pf_tesouro'.
        """
        try:
            postgres_conn_str = get_postgres_conn('postgres_mir')
            db = ClientPostgresDB(postgres_conn_str)
            db.remove_duplicates("nc_tesouro_pre_2026", COLUMN_MAPPING, schema="siafi")

        except Exception as e:
            logging.error(f"Erro ao executar a limpeza de duplicados: {str(e)}")
            raise

    fetch_and_ingest_task = PythonOperator(
        task_id="fetch_and_ingest",
        python_callable=fetch_and_ingest,
        provide_context=True,
    )

    clean_duplicates_task = PythonOperator(
        task_id="clean_duplicates",
        python_callable=clean_duplicates,
        provide_context=True,
    )

    fetch_and_ingest_task >> clean_duplicates_task
