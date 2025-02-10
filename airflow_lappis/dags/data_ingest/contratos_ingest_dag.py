import logging
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from postgres_helpers import get_postgres_conn
from cliente_contratos import ClienteContratos
from cliente_postgres import ClientPostgresDB


@dag(
    schedule_interval="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "Davi",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["contratos_api"],
)
def api_contratos_dag() -> None:
    """DAG para buscar e armazenar contratos de uma API no PostgreSQL."""

    @task
    def fetch_and_store_contratos() -> None:
        logging.info("[contratos_ingest_dag.py] Starting fetch_and_store_contratos task")
        api = ClienteContratos()
        postgres_conn_str = get_postgres_conn()
        db = ClientPostgresDB(postgres_conn_str)
        ug_codes = [113601, 113602]

        for ug_code in ug_codes:
            logging.info(
                f"[contratos_ingest_dag.py] Fetching contratos for UG code: {ug_code}"
            )
            contratos = api.get_contratos_by_ug(ug_code)
            if contratos:
                logging.info(
                    f"[contratos_ingest_dag.py] Inserting contratos for UG code: "
                    f"{ug_code} into PostgreSQL"
                )
                db.insert_data(
                    contratos,
                    "contratos",
                    conflict_fields=["id"],
                    primary_key=["id"],
                    schema="compras_gov",
                )
            else:
                logging.warning(
                    f"[contratos_ingest_dag.py] No contratos found for UG code: {ug_code}"
                )

    fetch_and_store_contratos()


dag_instance = api_contratos_dag()
