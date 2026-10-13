import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i8_ted_densidade import calcular_i8
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_SAIDA = "indicadores"

# Tabelas dbt lidas pelo indicador -> nome do argumento de calcular_i8
FONTES = {
    "planos": ("siafi_dbt", "planos_acao_ted"),
    "prog": ("siafi_dbt", "programas_ted"),
    "resumo": ("siafi_dbt", "ted_resumo_orcamentario"),
}


@dag(
    # Roda depois do mir_cosmos_dag (01:00), que materializa as fontes — mesmo
    # horário do I1/I4, já que lê fontes em comum, sem depender deles.
    schedule_interval=get_dynamic_schedule("i8_ted_densidade_dag", default="0 4 * * *"),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["indicadores", "I8", "MIR"],
)
def i8_ted_densidade_dag() -> None:
    """I8 (TED) — Densidade por Secretaria.

    Lê as tabelas dbt do TED, aplica a metodologia do BI
    (plugins/indicadores/i8_ted_densidade.py) e grava as quatro saídas do
    indicador no schema ``indicadores``, recalculadas do zero a cada execução.
    """

    @task
    def calcular_e_gravar_i8() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info(f"[I8] {argumento}: {len(linhas)} linhas lidas")

        saidas = calcular_i8(**fontes)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela, schema=SCHEMA_SAIDA)
            db.insert_data(linhas, tabela, schema=SCHEMA_SAIDA)
            logging.info(f"[I8] {SCHEMA_SAIDA}.{tabela}: {len(linhas)} linhas gravadas")

    calcular_e_gravar_i8()


i8_ted_densidade_dag()
