from typing import Dict, Any, List
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import logging
import json
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

                    # Se não tem mapeamento de colunas (recebidas), aplicar o
                    # mapeamento padrão.
                    if config["column_mapping"] is None:
                        if len(df.columns) == len(expected_columns):
                            df.columns = pd.Index(expected_columns)
                        else:
                            logging.warning(
                                "NCs %s anexo %s: N coluna incompatível:%s,%s",
                                email_type,
                                idx,
                                len(expected_columns),
                                len(df.columns),
                            )

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
