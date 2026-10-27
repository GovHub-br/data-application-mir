import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i9_municipios_atendidos import calcular_i9
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_SAIDA = "indicadores"

# Tabelas dbt lidas pelo indicador -> nome do argumento de calcular_i9.
# I9 só existe para Convênios/Fomentos (não se aplica ao TED) e lê as mesmas
# fontes do I1b: o I1 do Bloco 1 não gera mais saída por município.
FONTES = {
    "gold_convenios": ("siconv_dbt", "resumo_convenios"),
    "meta_crono_fisico": ("siconv_dbt", "convenio_meta_crono_fisico"),
}


@dag(
    # Roda depois do mir_cosmos_dag (01:00), que materializa as fontes. Não
    # depende mais da saída do I1; o horário foi mantido.
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

    Lê as tabelas dbt de convênios (gold + metas físicas), aplica a
    metodologia do BI (plugins/indicadores/i9_municipios_atendidos.py) e grava
    as duas saídas do indicador no schema ``indicadores``, recalculadas do
    zero a cada execução.
    """

    @task
    def calcular_e_gravar_i9() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info(f"[I9] {argumento}: {len(linhas)} linhas lidas")

        saidas = calcular_i9(**fontes)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela, schema=SCHEMA_SAIDA)
            db.insert_data(linhas, tabela, schema=SCHEMA_SAIDA)
            logging.info(f"[I9] {SCHEMA_SAIDA}.{tabela}: {len(linhas)} linhas gravadas")

    calcular_e_gravar_i9()


i9_municipios_atendidos_dag()
