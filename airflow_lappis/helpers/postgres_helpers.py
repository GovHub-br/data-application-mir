import logging
from airflow.providers.postgres.hooks.postgres import PostgresHook


def get_postgres_conn() -> str:
    try:
        hook = PostgresHook(postgres_conn_id="postgres_default")
        conn = hook.get_conn()
        schema = conn.info.dbname
        logging.info(
            f"[postgres_helpers] Obtained PostgreSQL connection: "
            f"dbname={schema}, user={conn.info.user},"
            f"host={conn.info.host}, port={conn.info.port}"
        )
        return (
            f"dbname={schema} user={conn.info.user} password={conn.info.password} "
            f"host={conn.info.host} port={conn.info.port}"
        )
    except Exception as e:
        logging.error(f"Failed to obtain PostgreSQL connection: {e}")
        raise
