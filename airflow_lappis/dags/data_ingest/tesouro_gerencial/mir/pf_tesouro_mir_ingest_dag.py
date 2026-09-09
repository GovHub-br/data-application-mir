from typing import Dict, Any, List
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import logging
import json
from schedule_loader import get_dynamic_schedule
from cliente_email import (
    fetch_email_with_zip,
    extract_csv_from_zip,
    resolve_email_date_range,
)
from email_ingest_params import date_range_params
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn

# Configurações básicas da DAG
default_args = {
    "owner": "Tiago",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Mapeamento das colunas para as programações financeiras (recebidas)
COLUMN_MAPPING = {
    0: "emissao_mes",
    1: "emissao_dia",
    2: "ug_emitente",
    3: "ug_emitente_descricao",
    4: "ug_favorecido",
    5: "ug_favorecido_descricao",
    6: "pf_evento",
    7: "pf_evento_descricao",
    8: "pf",
    9: "pf_inscricao",
    10: "pf_acao",
    11: "pf_acao_descricao",
    12: "pf_fonte_recursos",
    13: "pf_fonte_recursos_descricao",
    14: "doc_observacao",
    15: "pf_valor_linha",
}

# Assunto do email a ser processado
EMAIL_SUBJECT = "programacoes_financeiras"
SKIPROWS = 7

# Configurações da DAG
with DAG(
    dag_id="email_programacoes_financeiras_mir_ingest",
    default_args=default_args,
    description="Processa anexo consolidado de PFs por email e insere no db",
    schedule_interval=get_dynamic_schedule(
        "pf_tesouro_mir_ingest_dag", default="25 0 * * *"
    ),
    start_date=datetime(2023, 12, 1),
    catchup=False,
    params=date_range_params(),
    tags=["email", "pfs", "tesouro", "MIR"],
) as dag:

    def fetch_and_ingest(**context: Dict[str, Any]) -> Dict[str, int]:
        """Processa cada anexo e ingere imediatamente, evitando acúmulo em memória."""
        creds = json.loads(Variable.get("email_credentials"))

        EMAIL = creds["email"]
        PASSWORD = creds["password"]
        IMAP_SERVER = creds["imap_server"]
        SENDER_EMAIL = creds["sender_email"]
        params = context.get("params", {})
        data_inicial, data_final = resolve_email_date_range(
            params.get("data_inicial"), params.get("data_final")
        )

        logging.info("Iniciando o processamento do email de programações financeiras")
        zip_payloads: List[bytes] = fetch_email_with_zip(
            IMAP_SERVER,
            EMAIL,
            PASSWORD,
            SENDER_EMAIL,
            EMAIL_SUBJECT,
            start_date=data_inicial,
            end_date=data_final,
        )

        if not zip_payloads:
            logging.warning("Nenhum e-mail encontrado com o assunto configurado")
            return {"attachments": 0, "records": 0}

        logging.info("Total de anexos ZIP encontrados: %s", len(zip_payloads))

        postgres_conn_str = get_postgres_conn("postgres_mir")
        db = ClientPostgresDB(postgres_conn_str)
        total_records = 0

        for idx, payload in enumerate(zip_payloads, 1):
            df = extract_csv_from_zip(payload, COLUMN_MAPPING, SKIPROWS)
            if df is None or df.empty:
                logging.warning("Anexo %s ignorado (CSV inválido/vazio).", idx)
                continue

            data = df.to_dict(orient="records")
            for record in data:
                record["dt_ingest"] = datetime.now().isoformat()

            db.insert_data(data, "pf_tesouro", schema="siafi")
            total_records += len(data)
            logging.info("Anexo %s: %s registros inseridos", idx, len(data))
            del df, data

        logging.info("Total: %s anexos, %s registros", len(zip_payloads), total_records)
        return {"attachments": len(zip_payloads), "records": total_records}

    def clean_duplicates(**context: Dict[str, Any]) -> None:
        """
        Task para remover duplicados da tabela 'siafi.pf_tesouro'.
        """
        try:
            postgres_conn_str = get_postgres_conn("postgres_mir")
            db = ClientPostgresDB(postgres_conn_str)
            db.remove_duplicates("pf_tesouro", COLUMN_MAPPING, schema="siafi")

        except Exception as e:
            logging.error(f"Erro ao executar a limpeza de duplicados: {str(e)}")
            raise

    # Tarefa 1: Buscar os anexos e inserir no db, anexo a anexo
    fetch_and_ingest_task = PythonOperator(
        task_id="fetch_and_ingest",
        python_callable=fetch_and_ingest,
    )

    # Tarefa 2: Limpar duplicados no banco de dados
    clean_duplicates_task = PythonOperator(
        task_id="clean_duplicates",
        python_callable=clean_duplicates,
        provide_context=True,
    )

    # Fluxo da DAG
    fetch_and_ingest_task >> clean_duplicates_task
