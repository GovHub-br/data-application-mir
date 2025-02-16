import os
from datetime import datetime
from cosmos import DbtDag, ProjectConfig, ProfileConfig, ExecutionConfig

profile_config = ProfileConfig(
    profiles_yml_filepath=f"{os.environ['AIRFLOW_HOME']}/dags/dbt/ipea/profiles.yml",
    profile_name="ipea",
    target_name="prod",
)

my_cosmos_dag = DbtDag(
    project_config=ProjectConfig(f"{os.environ['AIRFLOW_HOME']}/dags/dbt/ipea"),
    profile_config=profile_config,
    execution_config=ExecutionConfig(
        dbt_executable_path=f"{os.environ['AIRFLOW_HOME']}/.local/bin/dbt",
    ),
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    dag_id="ipea_cosmos_dag",
    default_args={"retries": 2},
)
