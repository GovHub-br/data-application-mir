import logging
from airflow.decorators import dag, task
from airflow.models.baseoperator import chain
from datetime import datetime, timedelta
from schedule_loader import get_dynamic_schedule
from postgres_helpers import get_postgres_conn
from cliente_postgres import ClientPostgresDB
from cliente_ted import ClienteTed
from ingestao_ted import ENDPOINTS_TED, EndpointTed, ingerir_endpoint


@dag(
    schedule_interval=get_dynamic_schedule("ted_complementar_ingest_mir_dag"),
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "Joao",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["ted_api", "MIR", "coleta_mir"],
)
def ted_complementar_mir_dag() -> None:
    """Endpoints da API de TED alem de programa, plano_acao, nota_credito e
    programacao_financeira (que tem DAGs proprias): metas, etapas, termo de
    execucao, analises, pareceres, eventos das NCs, TRF das PFs, acoes
    orcamentarias e beneficiarios dos programas. Depende das DAGs de planos de
    acao, notas de credito, programacao financeira e programas."""

    def criar_task(endpoint: EndpointTed):
        @task(task_id=f"ingerir_{endpoint.tabela_api}")
        def ingerir() -> None:
            db = ClientPostgresDB(get_postgres_conn("postgres_mir"))
            gravadas = ingerir_endpoint(
                ClienteTed(), db, endpoint, datetime.now().isoformat()
            )
            logging.info(f"{endpoint.tabela_api}: {gravadas} linhas")

        return ingerir()

    chain(*[criar_task(endpoint) for endpoint in ENDPOINTS_TED])


ted_complementar_mir_dag()
