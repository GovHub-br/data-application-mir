{{ config(materialized="table") }}

with
    programa_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            titulo::text as titulo,
            tipo::text as tipo,
            orgao::text as orgao,
            publico_alvo::text as publico_alvo,
            descricao_do_problema::text as descricao_do_problema,
            causa_do_problema::text as causa_do_problema,
            evidencias_do_problema::text as evidencias_do_problema,
            justificativa_para_a_intervencao::text as justificativa_para_a_intervencao,
            evolucao_historica::text as evolucao_historica,
            comparacoes_internacionais::text as comparacoes_internacionais,
            relacao_com_os_ods::text as relacao_com_os_ods,
            agentes_envolvidos::text as agentes_envolvidos,
            articulacao_federativa::text as articulacao_federativa,
            enfoque_transversal::text as enfoque_transversal,
            marco_legal::text as marco_legal,
            planos_nacionais_setoriais_e_regionais::text
            as planos_nacionais_setoriais_e_regionais,
            {{ parse_financial_value("despesa_corrente_1o_ano_ppa") }}
            as despesa_corrente_1o_ano_ppa,
            {{ parse_financial_value("despesa_capital_1o_ano_ppa") }}
            as despesa_capital_1o_ano_ppa,
            {{
                parse_financial_value(
                    "orcamento_investimento_empresas_estatais_1o_ano_ppa"
                )
            }} as orcamento_investimento_empresas_estatais_1o_ano_ppa,
            {{ parse_financial_value("gastos_tributarios_1o_ano_ppa") }}
            as gastos_tributarios_1o_ano_ppa,
            {{ parse_financial_value("outras_fontes_1o_ano_ppa") }}
            as outras_fontes_1o_ano_ppa,
            {{ parse_financial_value("despesa_corrente_2o_ano_ppa") }}
            as despesa_corrente_2o_ano_ppa,
            {{ parse_financial_value("despesa_capital_2o_ano_ppa") }}
            as despesa_capital_2o_ano_ppa,
            {{
                parse_financial_value(
                    "orcamento_investimento_empresas_estatais_2o_ano_ppa"
                )
            }} as orcamento_investimento_empresas_estatais_2o_ano_ppa,
            {{ parse_financial_value("gastos_tributarios_2o_ano_ppa") }}
            as gastos_tributarios_2o_ano_ppa,
            {{ parse_financial_value("outras_fontes_2o_ano_ppa") }}
            as outras_fontes_2o_ano_ppa,
            {{ parse_financial_value("despesa_corrente_3o_ano_ppa") }}
            as despesa_corrente_3o_ano_ppa,
            {{ parse_financial_value("despesa_capital_3o_ano_ppa") }}
            as despesa_capital_3o_ano_ppa,
            {{
                parse_financial_value(
                    "orcamento_investimento_empresas_estatais_3o_ano_ppa"
                )
            }} as orcamento_investimento_empresas_estatais_3o_ano_ppa,
            {{ parse_financial_value("gastos_tributarios_3o_ano_ppa") }}
            as gastos_tributarios_3o_ano_ppa,
            {{ parse_financial_value("outras_fontes_3o_ano_ppa") }}
            as outras_fontes_3o_ano_ppa,
            {{ parse_financial_value("despesa_corrente_4o_ano_ppa") }}
            as despesa_corrente_4o_ano_ppa,
            {{ parse_financial_value("despesa_capital_4o_ano_ppa") }}
            as despesa_capital_4o_ano_ppa,
            {{
                parse_financial_value(
                    "orcamento_investimento_empresas_estatais_4o_ano_ppa"
                )
            }} as orcamento_investimento_empresas_estatais_4o_ano_ppa,
            {{ parse_financial_value("gastos_tributarios_4o_ano_ppa") }}
            as gastos_tributarios_4o_ano_ppa,
            {{ parse_financial_value("outras_fontes_4o_ano_ppa") }}
            as outras_fontes_4o_ano_ppa,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "programa") }}
    )

select *
from programa_raw
