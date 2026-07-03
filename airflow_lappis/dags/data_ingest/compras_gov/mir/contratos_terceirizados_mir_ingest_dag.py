import logging
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from schedule_loader import get_dynamic_schedule
from cliente_contratos import ClienteContratos
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn


@dag(
    dag_id="contratos_terceirizados_mir_ingest_dag",
    schedule_interval=get_dynamic_schedule("contratos_terceirizados_mir_ingest_dag"),
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "Luana",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["terceirizados_api", "compras_gov", "MIR"],
)
def api_terceirizados_mir_dag() -> None:
    """DAG para buscar e armazenar terceirizados no PostgreSQL do MIR."""

    @task
    def fetch_terceirizados() -> None:
        logging.info("[contratos_terceirizados_mir_ingest_dag.py] Starting fetch_terceirizados task")
        api = ClienteContratos()
        postgres_conn_str = get_postgres_conn("postgres_mir")  
        db = ClientPostgresDB(postgres_conn_str)
        contratos_ids = db.get_contratos_ids()

        for contrato_id in contratos_ids:
            try:
                logging.info(
                    f"[contratos_terceirizados_mir_ingest_dag.py] Fetching terceirizados for contrato ID: "
                    f"{contrato_id}"
                )
                terceirizados = api.get_terceirizados_by_contrato_id(str(contrato_id))

                if terceirizados:
                    for fatura in terceirizados:
                        fatura["dt_ingest"] = datetime.now().isoformat()

                db.insert_data(
                    terceirizados,
                    "terceirizados",
                    conflict_fields=["id"],
                    primary_key=["id"],
                    schema="compras_gov",
                )
            except Exception as e:
                logging.error(
                    f"[contratos_terceirizados_mir_ingest_dag.py] Error for contrato ID {contrato_id}: {e}"
                )

    fetch_terceirizados()


dag_instance = api_terceirizados_mir_dag()