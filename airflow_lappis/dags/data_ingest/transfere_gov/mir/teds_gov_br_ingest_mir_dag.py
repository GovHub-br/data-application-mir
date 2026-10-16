import logging
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from schedule_loader import get_dynamic_schedule
from postgres_helpers import get_postgres_conn
from cliente_transferencias_gov_br import ClienteTransferenciasGovBr
from cliente_postgres import ClientPostgresDB


@dag(
    schedule_interval=get_dynamic_schedule("teds_gov_br_ingest_mir_dag"),
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["ted", "gov_br", "MIR"],
)
def teds_gov_br_mir_dag() -> None:
    """
    Raspa as páginas de transferências voluntárias do MIR no gov.br, que ligam o
    número/ano do TED (ex.: "05/2026", como aparece nas NEs) ao número da
    transferência no Transferegov.

    Cada execução grava um retrato completo, com o mesmo dt_ingest em todas as
    linhas: a página às vezes repete o número/ano para TEDs diferentes, então não
    há chave natural, e o bronze lê só o retrato mais recente.

    As descentralizações de crédito sem TED (tedinhos, "Descentralização de Crédito
    ... Processo: ...") vão para descentralizacoes_gov_br, no mesmo retrato.
    """

    @task
    def fetch_and_store_teds_gov_br() -> None:
        api = ClienteTransferenciasGovBr()
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        paginas = api.listar_paginas()
        if not paginas:
            raise ValueError("Nenhuma subpágina de transferências encontrada")

        dt_ingest = datetime.now().isoformat()
        registros = []
        descentralizacoes = []
        for pagina in paginas:
            teds, descs = api.get_transferencias_pagina(pagina)
            for ordem, ted in enumerate(teds, start=1):
                registros.append({**ted, "ordem": ordem, "dt_ingest": dt_ingest})
            for ordem, desc in enumerate(descs, start=1):
                descentralizacoes.append({**desc, "ordem": ordem, "dt_ingest": dt_ingest})

        if not registros:
            raise ValueError("Nenhum TED extraído das páginas do gov.br")

        db.insert_data(registros, "teds_gov_br", schema="transfere_gov")
        if descentralizacoes:
            db.insert_data(
                descentralizacoes, "descentralizacoes_gov_br", schema="transfere_gov"
            )
        logging.info(
            f"{len(registros)} TEDs e {len(descentralizacoes)} descentralizações de "
            f"{len(paginas)} páginas do gov.br gravados"
        )

    fetch_and_store_teds_gov_br()


teds_gov_br_mir_dag()
