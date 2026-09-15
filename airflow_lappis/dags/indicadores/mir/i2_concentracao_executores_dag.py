import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i2_concentracao_executores import calcular_i2
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_INDICADORES = "indicadores"

# Tabelas lidas pelo indicador -> nome do argumento de calcular_i2.
# São SAÍDAS do I1 (schema indicadores), não tabelas dbt — ver docstring de
# indicadores/i2_concentracao_executores.py.
FONTES = {
    "teds_i1": (SCHEMA_INDICADORES, "i1_ted_por_instrumento"),
    "convenios_i1": (SCHEMA_INDICADORES, "i1_convenios_por_instrumento"),
}


@dag(
    # Roda depois do i1_valor_executado_dag (04:00): este indicador depende
    # da saída do I1 já estar gravada em indicadores.i1_*.
    schedule_interval=get_dynamic_schedule(
        "i2_concentracao_executores_dag", default="0 5 * * *"
    ),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["indicadores", "I2", "MIR"],
)
def i2_concentracao_executores_dag() -> None:
    """I2 — Concentração Institucional dos Executores.

    Lê a saída do I1 (schema ``indicadores``), aplica a metodologia do BI
    (plugins/indicadores/i2_concentracao_executores.py) e grava as seis
    saídas do indicador no schema ``indicadores``, recalculadas do zero a
    cada execução.
    """

    @task
    def calcular_e_gravar_i2() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info(f"[I2] {argumento}: {len(linhas)} linhas lidas")

        saidas = calcular_i2(**fontes)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela, schema=SCHEMA_INDICADORES)
            db.insert_data(linhas, tabela, schema=SCHEMA_INDICADORES)
            logging.info(
                f"[I2] {SCHEMA_INDICADORES}.{tabela}: {len(linhas)} linhas gravadas"
            )

    calcular_e_gravar_i2()


i2_concentracao_executores_dag()
