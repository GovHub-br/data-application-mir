import os
from datetime import datetime
from cosmos import DbtDag, ProjectConfig, ProfileConfig, ExecutionConfig, RenderConfig
from cosmos.constants import DBT_LOG_PATH_ENVVAR

dbt_log_path = "/tmp/dbt_logs" # NOSONAR
os.makedirs(dbt_log_path, exist_ok=True)
os.environ[DBT_LOG_PATH_ENVVAR] = dbt_log_path

profile_config = ProfileConfig(
    profiles_yml_filepath=f"{os.environ['AIRFLOW_REPO_BASE']}/dags/dbt/mir/profiles.yml",
    profile_name="mir",
    target_name="prod",
)

my_cosmos_dag = DbtDag(
    project_config=ProjectConfig(f"{os.environ['AIRFLOW_REPO_BASE']}/dags/dbt/mir"),
    profile_config=profile_config,
    execution_config=ExecutionConfig(
        dbt_executable_path=f"{os.environ['AIRFLOW_REPO_BASE']}/.local/bin/dbt",
    ),
    # Testes que referenciam mais de um modelo viram uma task própria, que roda
    # depois de todos os pais. Sem isso o Cosmos os executa junto ao primeiro
    # pai, antes dos demais existirem, e a task falha com "relation does not exist"
    render_config=RenderConfig(should_detach_multiple_parents_tests=True),
    # Expressãp cron para agendar a execução do DAG diariamente às 01:00
    # Futuralmente isso pode ser substituído por um cronograma mais específico
    # com dependências entre os DAGs
    schedule_interval=" 0 1 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    dag_id="mir_cosmos_dag",
    default_args={"retries": 2},
)
