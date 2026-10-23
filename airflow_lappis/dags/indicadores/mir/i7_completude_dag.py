import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from cliente_postgres import ClientPostgresDB
from indicadores.i7_completude import (
    build_completude_query,
    completude_tabela_from_stats,
    consolidar_i7,
)
from postgres_helpers import get_postgres_conn
from schedule_loader import get_dynamic_schedule

SCHEMA_INDICADORES = "indicadores"

# "Pasta" (TEDs/Convênios/Emendas, do script original) -> (schema, tabelas bronze).
# Mapeamento alinhado com a usuária: bronze é a camada mais próxima do dado
# bruto que existe no pipeline hoje. Convênios bate com os "16 arquivos" que
# a BI registrou no script original — mesma contagem de models em
# models/siconv_dbt/bronze/.
#
# TEDs e Emendas já chegam filtrados ao MIR no ingest (transfere_gov/mir/ e
# transferegov_emendas/mir/). Convênios vêm do ZIP público do SICONV (todos
# os ministérios) e recebem o filtro MIR via JOIN em tempo de execução —
# ver SICONV_MIR_JOINS abaixo.
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

# Filtro MIR para as tabelas siconv_dbt, via JOIN até proposta.cod_orgao_sup.
# Usar cod_orgao_sup = 67000 (órgão superior do MIR) cobre 748 convênios,
# incluindo os que têm ug_emitente NULL — contra 608 de ug_emitente = 810008.
# Tabelas com id_proposta: join direto a proposta.
# Tabelas sem id_proposta: passam por convenio para chegar a proposta.
_VIA_ID_PROPOSTA = (
    "LEFT JOIN siconv_dbt.proposta p ON t.id_proposta = p.id_proposta",
    "p.cod_orgao_sup = 67000",
)
_VIA_NR_CONVENIO = (
    "LEFT JOIN siconv_dbt.convenio c ON t.nr_convenio = c.nr_convenio "
    "LEFT JOIN siconv_dbt.proposta p ON c.id_proposta = p.id_proposta",
    "p.cod_orgao_sup = 67000",
)
SICONV_MIR_JOINS: dict[str, tuple[str, str]] = {
    "convenio":               _VIA_ID_PROPOSTA,
    "proposta":               ("", "t.cod_orgao_sup = 67000"),
    "cronograma_desembolso":  _VIA_ID_PROPOSTA,
    "meta_crono_fisico":      _VIA_ID_PROPOSTA,
    "historico_situacao":     _VIA_ID_PROPOSTA,
    **{
        tabela: _VIA_NR_CONVENIO
        for tabela in [
            "empenho", "desbloqueio", "prorroga_oficio", "solicitacao_alteracao",
            "termo_aditivo", "pagamento_tributo", "pagamento",
            "ingresso_contrapartida", "desembolso", "licitacao",
            "solicitacao_rendimento_aplicacao",
        ]
    },
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

    O cálculo de completude é feito inteiramente em SQL (COUNT(*) FILTER
    por coluna) — nenhuma linha de dado chega ao Python. Isso elimina o
    pico de memória que matava o worker com as bronzes grandes do SICONV.
    """

    @task
    def calcular_e_gravar_i7() -> None:
        db = ClientPostgresDB(get_postgres_conn("postgres_mir"))

        linhas_colunas: list[dict] = []
        linhas_tabelas: list[dict] = []
        for pasta, (schema, nomes_tabelas) in FONTES.items():
            for nome_tabela in sorted(nomes_tabelas):
                columns = db.get_table_columns(schema, nome_tabela)
                if not columns:
                    logging.info(f"[I7] {pasta}/{nome_tabela}: sem colunas, ignorada")
                    continue

                if schema == "siconv_dbt":
                    join_sql, mir_cond = SICONV_MIR_JOINS[nome_tabela]
                else:
                    join_sql, mir_cond = "", None

                query = build_completude_query(
                    schema, nome_tabela, columns, join_sql, mir_cond
                )
                n_registros, ausentes_por_col = db.execute_completude_stats(
                    query, columns
                )
                logging.info(f"[I7] {pasta}/{nome_tabela}: {n_registros} registros")

                cols, resumo = completude_tabela_from_stats(
                    pasta, nome_tabela, n_registros, ausentes_por_col
                )
                if resumo is None:
                    continue
                linhas_colunas.extend(cols)
                linhas_tabelas.append(resumo)

        saidas = consolidar_i7(linhas_colunas, linhas_tabelas)

        dt_calculo = datetime.now().isoformat()
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            db.drop_table_if_exists(tabela, schema=SCHEMA_INDICADORES)
            db.insert_data(linhas, tabela, schema=SCHEMA_INDICADORES)
            logging.info(
                f"[I7] {SCHEMA_INDICADORES}.{tabela}: {len(linhas)} linhas gravadas"
            )

    calcular_e_gravar_i7()


i7_completude_dag()
