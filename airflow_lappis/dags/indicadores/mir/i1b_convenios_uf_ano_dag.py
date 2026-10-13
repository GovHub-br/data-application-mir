import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i1b_convenios_uf_ano import calcular_i1b
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_SAIDA = "indicadores"

# Tabelas dbt lidas pelo indicador -> nome do argumento de calcular_i1b
FONTES = {
    "gold_convenios": ("siconv_dbt", "resumo_convenios"),
    "meta_crono_fisico": ("siconv_dbt", "convenio_meta_crono_fisico"),
}


@dag(
    # Roda depois do mir_cosmos_dag (01:00), que materializa as fontes — mesmo
    # horário do I1, já que lê fontes em comum, sem depender dele.
    schedule_interval=get_dynamic_schedule("i1b_convenios_uf_ano_dag", default="0 4 * * *"),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["indicadores", "I1b", "MIR"],
)
def i1b_convenios_uf_ano_dag() -> None:
    """I1b — Taxa de Execução por UF e Ano (Convênios/Fomentos).

    Lê as tabelas dbt de convênios (gold + metas físicas), aplica a
    metodologia do BI (plugins/indicadores/i1b_convenios_uf_ano.py) e grava
    as três saídas do indicador no schema ``indicadores``, recalculadas do
    zero a cada execução.
    """

    @task
    def calcular_e_gravar_i1b() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info(f"[I1b] {argumento}: {len(linhas)} linhas lidas")

        saidas = calcular_i1b(**fontes)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela, schema=SCHEMA_SAIDA)
            db.insert_data(linhas, tabela, schema=SCHEMA_SAIDA)
            logging.info(f"[I1b] {SCHEMA_SAIDA}.{tabela}: {len(linhas)} linhas gravadas")

    calcular_e_gravar_i1b()


i1b_convenios_uf_ano_dag()
