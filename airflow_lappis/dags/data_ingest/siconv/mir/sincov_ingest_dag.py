import logging
from datetime import datetime, timedelta
from airflow.decorators import dag, task
import psycopg2
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule
from cliente_postgres import ClientPostgresDB
from cliente_siconv import ClienteSiconv
from tabelas_siconv import TABELAS_SICONV


@dag(
    # Os zips do dia são publicados por volta das 08:15 (Last-Modified em 13/11/2026);
    # às 10:00 o dado do dia já está lá e entra no mir_cosmos_dag da madrugada seguinte.
    schedule_interval=get_dynamic_schedule("siconv_ingestao_dag", default="0 10 * * *"),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    # Duas execuções ao mesmo tempo disputariam o TRUNCATE das mesmas tabelas.
    max_active_runs=1,
    default_args={
        "owner": "Luana",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["siconv", "MIR"],
)
def siconv_ingestao_dag() -> None:

    @task
    def ingerir_tabela(
        nome_tabela: str,
        nome_csv: str,
        conflict_fields: list,
        primary_key: list,
        skip_rows: int,
        colunas: list,
        truncate_before_insert: bool = False,
        filtro_ids_sql: str = None,
    ) -> None:
        import os

        postgres_conn_str = get_postgres_conn("postgres_mir")

        logging.info(f"Iniciando ingestão da tabela {nome_tabela}")

        db = ClientPostgresDB(postgres_conn_str)
        cliente = ClienteSiconv()

        zip_path = cliente.baixar_zip(nome_csv)

        lote = []
        tamanho_lote = 5000
        total_inserido = 0

        conn = None
        try:
            conn = psycopg2.connect(postgres_conn_str)
            gerador_registros = cliente.ler_csv(
                zip_path, nome_csv, skip_rows, colunas_esperadas=colunas
            )

            # Tabela grande demais para guardar inteira: só entram as linhas cuja
            # primeira coluna está no resultado da consulta.
            if filtro_ids_sql:
                with conn.cursor() as cursor:
                    cursor.execute(filtro_ids_sql)
                    ids = {str(linha[0]) for linha in cursor.fetchall()}
                logging.info(f"Filtro de {nome_tabela}: {len(ids)} ids")
                chave = colunas[0].lower()
                gerador_registros = (
                    r for r in gerador_registros if r[chave] in ids
                )

            if truncate_before_insert:
                logging.info(f"Truncando tabela siconv.{nome_tabela}...")
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        DO $$ BEGIN
                        IF EXISTS (
                            SELECT FROM pg_tables 
                            WHERE schemaname = 'siconv' 
                            AND tablename = '{nome_tabela}'
                        ) THEN
                            TRUNCATE TABLE siconv.{nome_tabela};
                        END IF;
                        END $$;
                    """)

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
                        conn=conn,
                    )

                    total_inserido += len(lote)
                    logging.info(f"{total_inserido} registros processados...")
                    lote = []

            if lote:
                lote = [dict(t) for t in {tuple(d.items()) for d in lote}]

                db.insert_data(
                    lote,
                    nome_tabela,
                    conflict_fields=conflict_fields,
                    primary_key=primary_key,
                    schema="siconv",
                    conn=conn,
                )

                total_inserido += len(lote)

            # Sem commit, o TRUNCATE é desfeito e a tabela fica com a carga anterior.
            if truncate_before_insert and total_inserido == 0:
                raise ValueError(
                    f"Nenhum registro para siconv.{nome_tabela}; "
                    "a tabela não foi esvaziada"
                )

            conn.commit()
        finally:
            if conn is not None:
                conn.close()
            os.remove(zip_path)

        if total_inserido == 0:
            logging.warning(f"Nenhum registro processado para {nome_tabela}")
        else:
            logging.info(
                f"Ingestão finalizada: {total_inserido} registros em {nome_tabela}"
            )

    ultima_task = None

    for tabela in TABELAS_SICONV:
        task_atual = ingerir_tabela.override(task_id=f"ingerir_{tabela['nome_tabela']}")(
            nome_tabela=tabela["nome_tabela"],
            nome_csv=tabela["nome_csv"],
            conflict_fields=tabela["conflict_fields"],
            primary_key=tabela["primary_key"],
            skip_rows=tabela["skip_rows"],
            colunas=tabela["colunas"],
            truncate_before_insert=tabela.get("truncate_before_insert", False),
            filtro_ids_sql=tabela.get("filtro_ids_sql"),
        )

        if ultima_task is not None:
            ultima_task >> task_atual
        ultima_task = task_atual


siconv_ingestao_dag()
