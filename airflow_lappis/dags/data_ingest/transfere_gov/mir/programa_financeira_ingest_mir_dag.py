import logging
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from schedule_loader import get_dynamic_schedule
from postgres_helpers import get_postgres_conn
from cliente_postgres import ClientPostgresDB
from cliente_ted import ClienteTed, numeros_como_texto


@dag(
    schedule_interval=get_dynamic_schedule("programacao_financeira_ingest_mir_dag"),
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "Mateus",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["programacao_financeira", "ted_api", "MIR"],
)
def programacao_financeira_mir_dag() -> None:
    """Programação financeira dos planos de ação (endpoint programacao_financeira),
    por id_plano_acao.

    A API devolve o retrato completo, entao a carga substitui a tabela inteira
    (linhas removidas na fonte saem do banco). Se a API falhar para qualquer
    plano de ação, a DAG falha e a tabela fica como estava, sem gravar um retrato
    incompleto.
    """

    @task
    def fetch_and_store_programacao_financeira() -> None:
        api = ClienteTed()
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        linhas: list = []
        for id_plano_acao in db.get_id_planos_acao():
            dados = api.get_programacao_financeira_by_id_plano_acao(id_plano_acao)
            if dados is None:
                raise RuntimeError(
                    f"Falha na API de TED ao buscar programação financeira "
                    f"(id_plano_acao {id_plano_acao})"
                )
            linhas.extend(numeros_como_texto(dados))

        if not linhas:
            logging.warning("API de TED sem programação financeira; tabela mantida")
            return

        dt_ingest = datetime.now().isoformat()
        for linha in linhas:
            linha["dt_ingest"] = dt_ingest

        db.replace_rows(
            linhas,
            "programacao_financeira",
            delete_where="true",
            delete_params=(),
            schema="transfere_gov",
            preserva_nulos=True,
        )
        logging.info(
            f"{len(linhas)} linhas gravadas em transfere_gov.programacao_financeira"
        )

    fetch_and_store_programacao_financeira()


programacao_financeira_mir_dag()
