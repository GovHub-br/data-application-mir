import logging
from airflow.decorators import dag, task
from airflow.models import Variable
from datetime import datetime, timedelta
from schedule_loader import get_dynamic_schedule
from postgres_helpers import get_postgres_conn
from cliente_ted import ClienteTedPortal, plano_acao_portal_para_registro
from cliente_postgres import ClientPostgresDB


@dag(
    schedule_interval=get_dynamic_schedule("plano_acao_portal_ingest_mir_dag"),
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["ted_portal", "planos_acao", "MIR"],
)
def planos_acao_portal_mir_dag() -> None:
    """
    Complementa os planos de ação da API de dados abertos com o portal do sistema
    TED, que mostra antes a situação e o número do instrumento (ex.: TEDs de 2026
    já aprovados que nos dados abertos ainda aparecem em análise, sem número).
    """

    @task
    def fetch_and_store_planos_acao_portal() -> None:
        # Id do órgão no portal (unidadeDescentralizadoraFk). MIR = 308823.
        id_unidade = Variable.get(
            "airflow_orgao_ted_portal_unidade", default_var="308823"
        )
        logging.info(f"Buscando planos de ação no portal TED da unidade {id_unidade}")

        api = ClienteTedPortal()
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        planos = api.get_planos_acao_by_unidade_descentralizadora(id_unidade)
        if not planos:
            raise ValueError(
                f"Nenhum plano de ação retornado do portal para {id_unidade}"
            )

        registros = [plano_acao_portal_para_registro(p) for p in planos]
        for registro in registros:
            registro["dt_ingest"] = datetime.now().isoformat()

        db.insert_data(
            registros,
            "planos_acao_portal",
            primary_key=["id_plano_acao"],
            conflict_fields=["id_plano_acao"],
            schema="transfere_gov",
        )
        logging.info(f"{len(registros)} planos de ação do portal gravados")

    fetch_and_store_planos_acao_portal()


planos_acao_portal_mir_dag()
