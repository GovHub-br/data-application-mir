import logging
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from postgres_helpers import get_postgres_conn
from cliente_ted import ClienteTed
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
    tags=["ted_api", "programas"],
)
def api_programas_dag() -> None:

    @task
    def fetch_and_store_programas() -> None:
        logging.info("Starting api_programas_dag DAG")
        api = ClienteTed()
        postgres_conn_str = get_postgres_conn()
        db = ClientPostgresDB(postgres_conn_str)
        id_programas = db.get_id_programas()

        for id_programa in id_programas:
            programas = api.get_programa_by_id_programa(id_programa)
            if programas:
                logging.info("Inserting programas into PostgreSQL")

                db.insert_data(
                    programas,
                    "programas",
                    schema="ted",
                )
            else:
                logging.warning(f"No programas found for id_programas: {id_programas}")

    fetch_and_store_programas()


dag_instance = api_programas_dag()
