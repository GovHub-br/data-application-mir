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
    resolve_email_date_range,
)
from email_ingest_params import date_range_params
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn
from functools import partial

default_args = {
    "owner": "Mateus",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

pd.read_csv = partial(pd.read_csv, sep='\t', on_bad_lines='skip')

COLUMN_MAPPING_NC = {
    0: "emissao_dia",
    1: "nc",
    2: "emitente_codigo",
    3: "emitente_nome",
    4: "ptres",
    5: "fonte_codigo",
    6: "fonte_nome",
    7: "gnd_codigo",
    8: "gnd_nome",
    9: "pi_codigo",
    10: "pi_nome",
    11: "descricao",
    12: "ugr_codigo",
    13: "ugr_nome",
    14: "tipo_nc",
    15: "nc_item_detalhamento",
    16: "favorecido_codigo",
    17: "favorecido_nome",
    18: "ro",
    19: "nc_transferencia",
    20: "dc",
    21: "item_total",
    22: "total_lista",
    23: "valor_celula",
    24: "esfera_orcamentaria_codigo",
    25: "esfera_orcamentaria_nome",
    26: "emissao_ano",
    27: "emissao_mes",
}

EMAIL_SUBJECT = "notas_credito_mir_apos_2026"
SKIPROWS = 3

with DAG(
    dag_id="email_notas_credito_ingest_mir_pos_2026",
    default_args=default_args,
    schedule_interval=get_dynamic_schedule(
        "email_notas_credito_ingest_mir_post_2026", default="20 0 * * *"
    ),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    params=date_range_params(),
    tags=["MIR", "email", "notas_credito"],
) as dag:

    UNIQUE_KEY = [
        "nc",
        "emissao_dia",
        "emissao_mes",
        "emissao_ano",
        "ptres",
        "ugr_codigo",
        "valor_celula",
        "dc",
    ]

    def fetch_and_ingest(**context: Dict[str, Any]) -> Dict[str, int]:
        """Processa cada anexo e ingere imediatamente, evitando acúmulo em memória."""
        creds = json.loads(Variable.get("email_credentials"))
        params = context.get("params", {})
        data_inicial, data_final = resolve_email_date_range(
            params.get("data_inicial"), params.get("data_final")
        )

        logging.info("Iniciando coleta de emails para o assunto: %s", EMAIL_SUBJECT)
        zip_payloads: List[bytes] = fetch_email_with_zip(
            creds["imap_server"],
            creds["email"],
            creds["password"],
            creds["sender_email"],
            EMAIL_SUBJECT,
            start_date=data_inicial,
            end_date=data_final,
        )

        if not zip_payloads:
            logging.warning("Nenhum anexo ZIP encontrado.")
            return {"attachments": 0, "records": 0}

        logging.info("Total de anexos ZIP encontrados: %s", len(zip_payloads))

        postgres_conn_str = get_postgres_conn("postgres_mir")
        db = ClientPostgresDB(postgres_conn_str)
        total_records = 0

        for idx, payload in enumerate(zip_payloads, 1):
            df = extract_csv_from_zip(payload, COLUMN_MAPPING_NC, SKIPROWS)
            if df is None or df.empty:
                logging.warning("Anexo %s ignorado (CSV inválido/vazio).", idx)
                continue

            data = df.to_dict(orient="records")
            for record in data:
                record["dt_ingest"] = datetime.now().isoformat()

            db.insert_data(
                data,
                "nc_tesouro_pos__2026",
                conflict_fields=UNIQUE_KEY,
                primary_key=UNIQUE_KEY,
                schema="siafi",
            )
            total_records += len(data)
            logging.info("Anexo %s: %s registros inseridos", idx, len(data))
            del df, data

        logging.info("Total: %s anexos, %s registros", len(zip_payloads), total_records)
        return {"attachments": len(zip_payloads), "records": total_records}

    PythonOperator(
        task_id="fetch_and_ingest",
        python_callable=fetch_and_ingest,
    )
