import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i3_publico_alvo import calcular_i3
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_INDICADORES = "indicadores"

# Tabelas dbt lidas pelo indicador -> nome do argumento de calcular_i3.
# Mesmas fontes do I1 (não a saída do I1) — I3 precisa do texto de objeto/
# justificativa, que a saída do I1 não carrega.
FONTES = {
    "planos": ("siafi_dbt", "planos_acao_ted"),
    "resumo": ("siafi_dbt", "ted_resumo_orcamentario"),
    "instrumentos_emendas": ("emendas", "instrumentos_emendas"),
    "gold_convenios": ("siconv_dbt", "resumo_convenios"),
}


@dag(
    # Roda depois do mir_cosmos_dag (01:00), que materializa as fontes dbt —
    # mesmo horário do I1, já que lê as mesmas tabelas, sem depender dele.
    schedule_interval=get_dynamic_schedule("i3_publico_alvo_dag", default="0 4 * * *"),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["indicadores", "I3", "MIR"],
)
def i3_publico_alvo_dag() -> None:
    """I3 — Instrumentos com Público-Alvo Racializado.

    Lê as tabelas dbt (TED, convênios, emendas), aplica a metodologia do BI
    (plugins/indicadores/i3_publico_alvo.py) e grava as quatro saídas do
    indicador no schema ``indicadores``, recalculadas do zero a cada execução.
    """

    @task
    def calcular_e_gravar_i3() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info(f"[I3] {argumento}: {len(linhas)} linhas lidas")

        saidas = calcular_i3(**fontes)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela, schema=SCHEMA_INDICADORES)
            db.insert_data(linhas, tabela, schema=SCHEMA_INDICADORES)
            logging.info(
                f"[I3] {SCHEMA_INDICADORES}.{tabela}: {len(linhas)} linhas gravadas"
            )

    calcular_e_gravar_i3()


i3_publico_alvo_dag()
