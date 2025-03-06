import logging
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from postgres_helpers import get_postgres_conn
from cliente_postgres import ClientPostgresDB
from cliente_ted import ClienteTed


@dag(
    schedule_interval="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "Davi",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["notas de credito", "ted_api"],
)
def notas_de_credito_dag() -> None:

    @task
    def fetch_and_store_notas_de_credito() -> None:

        api = ClienteTed()
        postgres_conn_str = get_postgres_conn()
        db = ClientPostgresDB(postgres_conn_str)
        ug_codes = [113601, 113602]

        for ug_code in ug_codes:
            notas_de_credito = api.get_notas_de_credito_by_ug(ug_code)
            if notas_de_credito:
                db.insert_data(
                    notas_de_credito,
                    "notas_de_credito",
                    conflict_fields=["id_nota"],
                    primary_key=["id_nota"],
                    schema="ted",
                )
            else:
                logging.warning(f"No notas de credito found for UG code: {ug_code}")

    fetch_and_store_notas_de_credito()


dag_instance = notas_de_credito_dag()
