import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i1_valor_executado import calcular_i1
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_SAIDA = "indicadores"

# Tabelas dbt lidas pelo indicador -> nome do argumento de calcular_i1
FONTES = {
    "planos": ("siafi_dbt", "planos_acao_ted"),
    "resumo": ("siafi_dbt", "ted_resumo_orcamentario"),
    "pf": ("siafi_dbt", "pf_unificado_planos_acao"),
    "nc": ("siafi_dbt", "nc_plano_acao"),
    "ne": ("siafi_dbt", "ted_empenhos_plano_acao"),
    "gold_convenios": ("siconv_dbt", "resumo_convenios"),
    "instrumentos_emendas": ("emendas", "instrumentos_emendas"),
}


@dag(
    # Roda depois do mir_cosmos_dag (01:00), que materializa as fontes.
    schedule_interval=get_dynamic_schedule("i1_valor_executado_dag", default="0 4 * * *"),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["indicadores", "I1", "MIR"],
)
def i1_valor_executado_dag() -> None:
    """I1 — Valor Executado por Instrumento.

    Lê as tabelas dbt (TED, convênios, emendas), aplica a metodologia do BI
    (plugins/indicadores/i1_valor_executado.py) e grava as seis saídas do
    indicador no schema ``indicadores``, recalculadas do zero a cada execução.
    """

    @task
    def calcular_e_gravar_i1() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info(f"[I1] {argumento}: {len(linhas)} linhas lidas")

        saidas = calcular_i1(**fontes)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela, schema=SCHEMA_SAIDA)
            db.insert_data(linhas, tabela, schema=SCHEMA_SAIDA)
            logging.info(f"[I1] {SCHEMA_SAIDA}.{tabela}: {len(linhas)} linhas gravadas")

    calcular_e_gravar_i1()


i1_valor_executado_dag()
