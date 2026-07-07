import logging
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from schedule_loader import get_dynamic_schedule
from cliente_contratos import ClienteContratos
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn


@dag(
    dag_id="contratos_cronograma_mir_ingest_dag",
    schedule_interval=get_dynamic_schedule("contratos_cronograma_mir_ingest_dag"),
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "Luana",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["cronograma_api", "compras_gov", "MIR"],
)
def api_cronograma_mir_dag() -> None:
    """DAG para buscar e armazenar cronograma no PostgreSQL do MIR."""

    @task
    def fetch_cronograma() -> None:
        logging.info("[contratos_cronograma_mir_ingest_dag.py] Starting fetch_cronograma task")
        api = ClienteContratos()
        postgres_conn_str = get_postgres_conn("postgres_mir")
        db = ClientPostgresDB(postgres_conn_str)
        contratos_ids = db.get_contratos_ids()

        for contrato_id in contratos_ids:
            try:
                logging.info(
                    f"[contratos_cronograma_mir_ingest_dag.py] Fetching cronograma for contrato ID: "
                    f"{contrato_id}"
                )
                cronograma = api.get_cronograma_by_contrato_id(str(contrato_id))

                if cronograma:
                    for item in cronograma:
                        item["contrato_id"] = contrato_id
                        item["dt_ingest"] = datetime.now().isoformat()

                db.insert_data(
                    cronograma,
                    "cronograma",
                    conflict_fields=["id", "contrato_id"],
                    primary_key=["id", "contrato_id"],
                    schema="compras_gov",
                )
            except Exception as e:
                logging.error(
                    f"[contratos_cronograma_mir_ingest_dag.py] Error for contrato ID {contrato_id}: {e}"
                )

    fetch_cronograma()


dag_instance = api_cronograma_mir_dag()