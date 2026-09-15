import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i9_municipios_atendidos import calcular_i9
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_INDICADORES = "indicadores"

# I9 só existe para Convênios/Fomentos (não se aplica ao TED) e lê a SAÍDA
# do I1 (schema indicadores), não tabelas dbt — mesma decisão do I2.
FONTE = (SCHEMA_INDICADORES, "i1_convenios_por_municipio")


@dag(
    # Roda depois do i1_valor_executado_dag (04:00): este indicador depende
    # da saída do I1 já estar gravada em indicadores.i1_convenios_por_municipio.
    schedule_interval=get_dynamic_schedule(
        "i9_municipios_atendidos_dag", default="0 5 * * *"
    ),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["indicadores", "I9", "MIR"],
)
def i9_municipios_atendidos_dag() -> None:
    """I9 — Municípios Atendidos (Convênios/Fomentos).

    Lê a saída do I1 (schema ``indicadores``), aplica a metodologia do BI
    (plugins/indicadores/i9_municipios_atendidos.py) e grava as duas saídas
    do indicador no schema ``indicadores``, recalculadas do zero a cada
    execução.
    """

    @task
    def calcular_e_gravar_i9() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        schema, tabela = FONTE
        convenios_por_municipio = db.fetch_table(schema, tabela)
        logging.info(f"[I9] {tabela}: {len(convenios_por_municipio)} linhas lidas")

        saidas = calcular_i9(convenios_por_municipio)

        dt_calculo = datetime.now().isoformat()
        for tabela_saida, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela_saida, schema=SCHEMA_INDICADORES)
            db.insert_data(linhas, tabela_saida, schema=SCHEMA_INDICADORES)
            logging.info(
                f"[I9] {SCHEMA_INDICADORES}.{tabela_saida}: {len(linhas)} linhas gravadas"
            )

    calcular_e_gravar_i9()


i9_municipios_atendidos_dag()
