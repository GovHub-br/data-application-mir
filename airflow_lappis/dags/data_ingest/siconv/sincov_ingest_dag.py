import logging
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from postgres_helpers import get_postgres_conn
from cliente_postgres import ClientPostgresDB
from cliente_siconv import ClienteSiconv
from tabelas_siconv import TABELAS_SICONV

@dag(
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={
        "owner": "Luana",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["siconv", "data_ingest"],
)
def siconv_ingestao_dag() -> None:

    @task
    def baixar_siconv() -> str:
        cliente = ClienteSiconv()
        cliente.baixar_zip()
        return cliente.ZIP_PATH

    @task
    def ingerir_tabela(zip_path: str, nome_tabela: str, nome_csv: str, conflict_fields: list, primary_key: list, skip_rows: int, colunas: list, truncate_before_insert: bool = False) -> None:
        logging.info(f"[siconv_ingest_dag.py] Iniciando ingestão da tabela {nome_tabela}")
        postgres_conn_str = get_postgres_conn("postgres_mir")
        db = ClientPostgresDB(postgres_conn_str)
        cliente = ClienteSiconv()

        if truncate_before_insert:
            logging.info(f"[siconv_ingest_dag.py] Truncando tabela siconv.{nome_tabela}...")
            db.execute_non_query(f"""
                DO $$ BEGIN
                 IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'siconv' AND tablename = '{nome_tabela}') THEN
                 TRUNCATE TABLE siconv.{nome_tabela};
                 END IF;
             END $$;
            """)
        gerador_registros = cliente.ler_csv(nome_csv, skip_rows, colunas_esperadas=colunas)

        lote = []
        tamanho_lote = 5000
        total_inserido = 0

        for registro in gerador_registros:
            lote.append(registro)
            
            if len(lote) >= tamanho_lote:
                lote = [dict(t) for t in {tuple(d.items()) for d in lote}]
                db.insert_data(
                    lote,
                    nome_tabela,
                    conflict_fields=conflict_fields,
                    primary_key=primary_key,
                    schema="siconv",
                )
                total_inserido += len(lote)
                logging.info(f"[siconv_ingest_dag.py] {total_inserido} registros processados...")
                lote = []

        if lote:
            lote = [dict(t) for t in {tuple(d.items()) for d in lote}]
            db.insert_data(
                lote,
                nome_tabela,
                conflict_fields=conflict_fields,
                primary_key=primary_key,
                schema="siconv",
            )
            total_inserido += len(lote)

        if total_inserido == 0:
            logging.warning(f"[siconv_ingest_dag.py] Nenhum registro processado para {nome_tabela}")
        else:
            logging.info(f"[siconv_ingest_dag.py] Ingestão finalizada: {total_inserido} registros em {nome_tabela}")

    path_zip = baixar_siconv()

    ultima_task = path_zip

    for tabela in TABELAS_SICONV:
        task_atual = ingerir_tabela.override(task_id=f"ingerir_{tabela['nome_tabela']}")(
            zip_path=path_zip,
            nome_tabela=tabela["nome_tabela"],
            nome_csv=tabela["nome_csv"],
            conflict_fields=tabela["conflict_fields"],
            primary_key=tabela["primary_key"],
            skip_rows=tabela["skip_rows"],
            colunas=tabela["colunas"],
            truncate_before_insert=tabela.get("truncate_before_insert", False),
        )

        ultima_task >> task_atual
        ultima_task = task_atual

siconv_ingestao_dag()