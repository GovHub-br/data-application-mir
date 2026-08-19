{{ config(materialized="table") }}

with
    acao_nao_orcamentaria_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            acao_nao_orcamentaria::text as acao_nao_orcamentaria,
            descricao::text as descricao,
            tipo::text as tipo,
            fonte_de_informacoes::text as fonte_de_informacoes,
            fonte_de_recursos::text as fonte_de_recursos,
            especificacao_da_outra_fonte_de_financiamento::text
            as especificacao_da_outra_fonte_de_financiamento,
            {{ parse_financial_value("valor_total") }} as valor_total,
            {{ parse_financial_value("valor_previsto_para_o_1o_ano_do_ppa") }}
            as valor_previsto_para_o_1o_ano_do_ppa,
            {{ parse_financial_value("valor_previsto_para_o_2o_ano_do_ppa") }}
            as valor_previsto_para_o_2o_ano_do_ppa,
            {{ parse_financial_value("valor_previsto_para_o_3o_ano_do_ppa") }}
            as valor_previsto_para_o_3o_ano_do_ppa,
            {{ parse_financial_value("valor_previsto_para_o_4o_ano_do_ppa") }}
            as valor_previsto_para_o_4o_ano_do_ppa,
            produto::text as produto,
            especificacao_do_produto::text as especificacao_do_produto,
            unidade_de_medida::text as unidade_de_medida,
            {{ parse_financial_value("meta_fisica") }} as meta_fisica,
            titulo::text as titulo,
            responsavel_pela_informacao::text as responsavel_pela_informacao,
            tributo::text as tributo,
            {{ parse_financial_value("valor_previsto_para_2028") }}
            as valor_previsto_para_2028,
            funcao::text as funcao,
            subfuncao::text as subfuncao,
            to_date(nullif(inicio_da_vigencia, ''), 'DD/MM/YYYY') as inicio_da_vigencia,
            to_date(nullif(termino_da_vigencia, ''), 'DD/MM/YYYY') as termino_da_vigencia,
            vigencia_indeterminada::text as vigencia_indeterminada,
            fonte_dos_dados::text as fonte_dos_dados,
            base_legal::text as base_legal,
            tipo_de_beneficiario::text as tipo_de_beneficiario,
            descricao_do_beneficiario::text as descricao_do_beneficiario,
            total_de_beneficiarios_previstos_1_ano_de_ppa::text
            as total_de_beneficiarios_previstos_1_ano_de_ppa,
            total_de_beneficiarios_previstos_2_ano_de_ppa::text
            as total_de_beneficiarios_previstos_2_ano_de_ppa,
            total_de_beneficiarios_previstos_3_ano_de_ppa::text
            as total_de_beneficiarios_previstos_3_ano_de_ppa,
            total_de_beneficiarios_previstos_4_ano_de_ppa::text
            as total_de_beneficiarios_previstos_4_ano_de_ppa,
            {{ parse_financial_value("valor_previsto_para_2029") }}
            as valor_previsto_para_2029,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "acao_nao_orcamentaria") }}
    )

select *
from acao_nao_orcamentaria_raw
