import json
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from cliente_email import fetch_email_with_zip, resolve_email_date_range
from email_ingest_params import date_range_params
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn
from relatorio_execucao_ted_ug import decodificar, parse_execucao_ted_ug
from schedule_loader import get_dynamic_schedule

default_args = {
    "owner": "João",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Relatório "Execução TED por UG" do Tesouro Gerencial: a consulta oficial do MIR
# para o gasto com TEDs (destaque recebido, crédito disponível, empenhado,
# liquidado e pago por UG executora). Ver relatorio_execucao_ted_ug.py.
TABLE_SCHEMA = "siafi"
TABLE_NAME = "execucao_ted_ug"
EMAIL_SUBJECT = "execucao_ted_por_ug"


with DAG(
    dag_id="email_execucao_ted_ug_ingest_dag",
    default_args=default_args,
    description=(
        "Processa o anexo do relatório Execução TED por UG vindo do email e "
        "substitui no db os anos que ele traz"
    ),
    schedule_interval=get_dynamic_schedule(
        "email_execucao_ted_ug_ingest_dag", default="5 0 * * *"
    ),
    start_date=datetime(2023, 12, 1),
    catchup=False,
    params=date_range_params(),
    tags=["MIR", "email", "ted", "tesouro"],
) as dag:

    def fetch_and_ingest(**context: Dict[str, Any]) -> Dict[str, int]:
        """
        Cada anexo é a posição acumulada (saldo) dos anos que ele traz: substitui
        as linhas desses anos, sem deduplicar por conteúdo. Os anexos vêm em
        ordem cronológica, então o mais recente prevalece. Ano que não vem no
        anexo (ex.: o relatório configurado só para o período corrente) fica como
        estava.
        """
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

        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))
        total_attachments = total_records = 0
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

            records = parse_execucao_ted_ug(decodificar(raw_data))
            if not records:
                logging.warning("Anexo %s sem linhas de dado.", idx)
                continue

            dt_ingest = datetime.now().isoformat()
            for record in records:
                record["dt_ingest"] = dt_ingest
            anos = sorted({r["ano_lancamento"] for r in records})
            db.replace_rows(
                records,
                TABLE_NAME,
                "ano_lancamento = ANY(%s)",
                (anos,),
                schema=TABLE_SCHEMA,
            )
            total_attachments += 1
            total_records += len(records)
            logging.info(
                "Anexo %s (anos %s): %s registros gravados", idx, anos, len(records)
            )

        logging.info("Total: %s anexos, %s registros", total_attachments, total_records)
        return {"attachments": total_attachments, "records": total_records}

    PythonOperator(
        task_id="fetch_and_ingest",
        python_callable=fetch_and_ingest,
    )
