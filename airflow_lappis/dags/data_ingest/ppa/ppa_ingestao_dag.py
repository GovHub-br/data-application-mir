import logging
import os
from datetime import datetime, timedelta
from typing import List

import psycopg2
from airflow.decorators import dag, task

from cliente_postgres import ClientPostgresDB
from cliente_ppa import ClientePPA
from postgres_helpers import get_postgres_conn
from tabelas_ppa import TABELAS_PPA

SCHEMA = "ppa"
POSTGRES_CONN_ID = "postgres_mir"
TAMANHO_LOTE = 5000

# Prefixo comum das URLs dos dados abertos do PPA/SIOP.
_PREFIXO = (
    "https://www.gov.br/planejamento/pt-br/assuntos/planejamento/plano-plurianual/"
    "arquivos/lei-do-ppa-2024-2027/"
)

# Links diretos dos .zip. Todos precisam do sufixo /@@display-file/file (Plone):
# sem ele, a URL "nua" do zip de 2024 devolve a página HTML, não o arquivo.
URL_PPA_2024 = _PREFIXO + "ppa-2024-2027-dados-abertos.zip/@@display-file/file"
URL_PPA_2025 = (
    _PREFIXO + "revisao-ppa-2025/ppa2024-2027_atualizado_2025.zip/@@display-file/file"
)
URL_PPA_2026 = (
    _PREFIXO + "revisao-2026/dados-abertos_ppa_2024_2027-revisao_2026.zip"
    "/@@display-file/file"
)

# Cada revisão contribui apenas os CSVs do seu próprio ano (ver tabelas_ppa.py).
ZIPS_PPA = [
    (2024, URL_PPA_2024),
    (2025, URL_PPA_2025),
    (2026, URL_PPA_2026),
]


def _inserir_lote(
    db: ClientPostgresDB,
    lote: List[dict],
    nome_tabela: str,
    conflict_fields: List[str],
    primary_key: List[str],
    conn: object,
) -> int:
    """Deduplica o lote por id_hash e insere/upserta, acrescentando dt_ingest."""
    unicos = {registro["id_hash"]: registro for registro in lote}
    registros = list(unicos.values())

    agora = datetime.now().isoformat()
    for registro in registros:
        registro["dt_ingest"] = agora

    db.insert_data(
        registros,
        nome_tabela,
        conflict_fields=conflict_fields,
        primary_key=primary_key,
        schema=SCHEMA,
        conn=conn,
    )
    return len(registros)


def _ingerir_tabela(
    zip_path: str,
    ano: int,
    nome_tabela: str,
    arquivo: str,
    conflict_fields: List[str],
    primary_key: List[str],
    skip_rows: int = 0,
) -> int:
    """Lê o CSV do ano em streaming e carrega em ppa.{nome_tabela} em lotes."""
    postgres_conn_str = get_postgres_conn(POSTGRES_CONN_ID)

    logging.info(
        "[ppa_ingestao_dag.py] Ingerindo %s (ano %s) de %s", nome_tabela, ano, arquivo
    )

    db = ClientPostgresDB(postgres_conn_str)
    cliente = ClientePPA(ano_ppa=ano)
    cliente.zip_path = zip_path

    gerador = cliente.ler_csv(arquivo, skip_rows=skip_rows)

    lote: List[dict] = []
    total_inserido = 0

    conn = psycopg2.connect(postgres_conn_str)
    try:
        for registro in gerador:
            lote.append(registro)
            if len(lote) >= TAMANHO_LOTE:
                total_inserido += _inserir_lote(
                    db, lote, nome_tabela, conflict_fields, primary_key, conn
                )
                logging.info(
                    "%s: %s registros processados...", nome_tabela, total_inserido
                )
                lote = []

        if lote:
            total_inserido += _inserir_lote(
                db, lote, nome_tabela, conflict_fields, primary_key, conn
            )

        conn.commit()
    finally:
        conn.close()

    if total_inserido == 0:
        logging.warning(
            "[ppa_ingestao_dag.py] Nenhum registro em %s (ano %s)", nome_tabela, ano
        )
    else:
        logging.info(
            "[ppa_ingestao_dag.py] %s: %s registros (ano %s)",
            nome_tabela,
            total_inserido,
            ano,
        )
    return total_inserido


@dag(
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={
        "owner": "Tiago",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["ppa", "siop", "MIR"],
)
def ppa_ingestao_dag() -> None:

    @task
    def baixar_ppa(ano: int, url: str) -> str:
        cliente = ClientePPA(ano_ppa=ano, url=url)
        return cliente.baixar_zip()

    @task
    def ingerir_tabela(
        zip_path: str,
        ano: int,
        nome_tabela: str,
        arquivo: str,
        conflict_fields: List[str],
        primary_key: List[str],
        skip_rows: int,
    ) -> None:
        _ingerir_tabela(
            zip_path=zip_path,
            ano=ano,
            nome_tabela=nome_tabela,
            arquivo=arquivo,
            conflict_fields=conflict_fields,
            primary_key=primary_key,
            skip_rows=skip_rows,
        )

    @task
    def deletar_zip(zip_path: str) -> None:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logging.info("[ppa_ingestao_dag.py] Arquivo %s deletado", zip_path)
        else:
            logging.warning("[ppa_ingestao_dag.py] Arquivo %s não encontrado", zip_path)

    # Encadeia as 3 revisões em sequência (um zip em disco por vez):
    # baixar_ppa_{ano} -> ingerir_{tabela}_{ano} (em série) -> deletar_zip_{ano}.
    fim_revisao_anterior = None
    for ano, url in ZIPS_PPA:
        path_zip = baixar_ppa.override(task_id=f"baixar_ppa_{ano}")(ano=ano, url=url)

        if fim_revisao_anterior is not None:
            fim_revisao_anterior >> path_zip

        ultima_task = path_zip
        for tabela in TABELAS_PPA:
            arquivo = tabela["arquivos"].get(ano)
            if not arquivo:
                continue
            task_ingestao = ingerir_tabela.override(
                task_id=f"ingerir_{tabela['nome_tabela']}_{ano}"
            )(
                zip_path=path_zip,
                ano=ano,
                nome_tabela=tabela["nome_tabela"],
                arquivo=arquivo,
                conflict_fields=tabela["conflict_fields"],
                primary_key=tabela["primary_key"],
                skip_rows=tabela["skip_rows"],
            )
            ultima_task >> task_ingestao
            ultima_task = task_ingestao

        limpeza = deletar_zip.override(task_id=f"deletar_zip_{ano}")(path_zip)
        ultima_task >> limpeza
        fim_revisao_anterior = limpeza


dag_instance = ppa_ingestao_dag()
