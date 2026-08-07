import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models import Variable
from cliente_onedrive import ClienteOneDrive
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule


@dag(
    schedule_interval=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "Mateus",
        "retries": 0,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["export", "onedrive", "MIR"],
)
def export_postgres_to_onedrive_dag() -> None:
    """Exporta tabelas configuradas do Postgres para CSV e envia para o
    OneDrive de um usuário via Microsoft Graph API."""

    @task
    def export_and_upload_tables() -> None:
        export_config = Variable.get("onedrive_export_config", deserialize_json=True)
        credentials = Variable.get("secret_onedrive_credentials", deserialize_json=True)

        tables = export_config.get("tables", [])
        onedrive_user_id = export_config["onedrive_user_id"]
        onedrive_folder = export_config.get("onedrive_folder", "")

        if not tables:
            logging.warning(
                "Nenhuma tabela configurada em 'onedrive_export_config.tables'."
            )
            return

        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))
        onedrive = ClienteOneDrive(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            tenant_id=credentials["tenant_id"],
        )

        for table_config in tables:
            schema = table_config["schema"]
            table = table_config["table"]
            file_name = table_config.get("file_name", f"{table}.csv")

            logging.info(f"Exportando {schema}.{table} do Postgres")
            csv_content = db.export_table_to_csv(schema, table)

            logging.info(f"Enviando {file_name} para o OneDrive de {onedrive_user_id}")
            onedrive.upload_file(
                user_id=onedrive_user_id,
                folder_path=onedrive_folder,
                file_name=file_name,
                content=csv_content.encode("utf-8-sig"),
            )
            logging.info(f"{file_name} enviado com sucesso para o OneDrive")

    export_and_upload_tables()


export_postgres_to_onedrive_dag()
