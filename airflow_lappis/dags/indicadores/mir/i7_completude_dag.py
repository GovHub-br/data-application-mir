import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i7_completude import completude_tabela, consolidar_i7
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_INDICADORES = "indicadores"

# "Pasta" (TEDs/Convênios/Emendas, do script original) -> (schema, tabelas bronze).
# Mapeamento alinhado com a usuária: bronze é a camada mais próxima do dado
# bruto que existe no pipeline hoje. Convênios bate com os "16 arquivos" que
# a BI registrou no script original — mesma contagem de models em
# models/siconv_dbt/bronze/.
FONTES = {
    # pf_ptres, pf_tesouro e pf_transfere têm alias customizado no model dbt
    # (config(alias="..._mir")) — o nome real da tabela no Postgres não é o
    # nome do arquivo .sql, ao contrário de todos os outros models bronze
    # deste projeto. Descoberto rodando a DAG contra o Postgres real
    # (UndefinedTable em siafi_dbt.pf_ptres).
    "TEDs": ("siafi_dbt", [
        "programas_ted", "pf_ptres_mir", "planos_acao_ted", "empenhos_tesouro_ted",
        "pf_tesouro_mir", "ppa_tesouro", "nc_tesouro_mir", "notas_de_credito",
        "pf_transfere_mir",
    ]),
    "Convênios": ("siconv_dbt", [
        "convenio", "empenho", "desbloqueio", "prorroga_oficio",
        "solicitacao_alteracao", "termo_aditivo", "pagamento_tributo",
        "cronograma_desembolso", "meta_crono_fisico", "pagamento",
        "ingresso_contrapartida", "desembolso", "licitacao", "proposta",
        "solicitacao_rendimento_aplicacao", "historico_situacao",
    ]),
    "Emendas": ("emendas", [
        "tg_emendas_dotacao", "relatorio_gestao_novo", "programas", "metas",
        "ordens_bancarias", "empenhos_especiais", "planos_trabalho_especial",
        "documentos_habeis", "finalidades", "tg_emendas", "planos_acoes",
        "historico_pagamentos", "executor", "relatorio_gestao",
    ]),
}


@dag(
    # Roda depois do mir_cosmos_dag (01:00), que materializa as bronzes lidas aqui.
    schedule_interval=get_dynamic_schedule("i7_completude_dag", default="0 4 * * *"),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "owner": "João",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["indicadores", "I7", "MIR"],
)
def i7_completude_dag() -> None:
    """I7 — Completude e Qualidade dos Dados.

    Lê as tabelas bronze do dbt (TED, Convênios, Emendas), aplica a
    metodologia do BI (plugins/indicadores/i7_completude.py) e grava as
    seis saídas do indicador no schema ``indicadores``, recalculadas do
    zero a cada execução.
    """

    @task
    def calcular_e_gravar_i7() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        # Processa uma tabela bronze por vez e descarta as linhas brutas em
        # seguida — algumas bronzes de Convênios têm milhões de linhas;
        # acumular todas em memória antes de calcular estourou o worker
        # (SIGKILL) na primeira execução real. Só o resultado agregado
        # (poucas linhas por tabela) fica retido até o fim.
        linhas_colunas: list[dict] = []
        linhas_tabelas: list[dict] = []
        for pasta, (schema, nomes_tabelas) in FONTES.items():
            for nome_tabela in sorted(nomes_tabelas):
                linhas = db.fetch_table(schema, nome_tabela)
                logging.info(f"[I7] {pasta}/{nome_tabela}: {len(linhas)} linhas lidas")

                cols, resumo = completude_tabela(pasta, nome_tabela, linhas)
                del linhas  # libera antes de ler a próxima tabela
                if resumo is None:
                    continue
                linhas_colunas.extend(cols)
                linhas_tabelas.append(resumo)

        saidas = consolidar_i7(linhas_colunas, linhas_tabelas)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # Indicador é recalculado inteiro: substitui a tabela em vez de upsert,
            # para não deixar linhas de agregações que deixaram de existir.
            db.drop_table_if_exists(tabela, schema=SCHEMA_INDICADORES)
            db.insert_data(linhas, tabela, schema=SCHEMA_INDICADORES)
            logging.info(
                f"[I7] {SCHEMA_INDICADORES}.{tabela}: {len(linhas)} linhas gravadas"
            )

    calcular_e_gravar_i7()


i7_completude_dag()
