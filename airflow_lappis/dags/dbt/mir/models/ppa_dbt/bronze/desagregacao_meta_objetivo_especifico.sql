{{ config(materialized="table") }}

with
    desagregacao_meta_objetivo_especifico_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            objetivo::text as objetivo,
            objetivo_especifico::text as objetivo_especifico,
            indicador::text as indicador,
            meta_do_objetivo_especifico::text as meta_do_objetivo_especifico,
            publico::text as publico,
            unidade_de_medida::text as unidade_de_medida,
            {{ parse_financial_value("valor_esperado_1o_ano_ppa") }}
            as valor_esperado_1o_ano_ppa,
            {{ parse_financial_value("valor_esperado_2o_ano_ppa") }}
            as valor_esperado_2o_ano_ppa,
            {{ parse_financial_value("valor_esperado_3o_ano_ppa") }}
            as valor_esperado_3o_ano_ppa,
            {{ parse_financial_value("meta_final_ppa") }} as meta_final_ppa,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "desagregacao_meta_objetivo_especifico") }}
    )

select *
from desagregacao_meta_objetivo_especifico_raw
