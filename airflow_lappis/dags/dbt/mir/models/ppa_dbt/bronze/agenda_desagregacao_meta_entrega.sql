{{ config(materialized="table") }}

with
    agenda_desagregacao_meta_entrega_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            codigo_agenda::text as codigo_agenda,
            programa::text as programa,
            objetivo::text as objetivo,
            objetivo_especifico::text as objetivo_especifico,
            entrega::text as entrega,
            indicador::text as indicador,
            meta_da_entrega::text as meta_da_entrega,
            publico::text as publico,
            unidade_de_medida::text as unidade_de_medida,
            {{ parse_financial_value("valor_esperado_1o_ano_ppa") }}
            as valor_esperado_1o_ano_ppa,
            {{ parse_financial_value("valor_esperado_2o_ano_ppa") }}
            as valor_esperado_2o_ano_ppa,
            {{ parse_financial_value("valor_esperado_3o_ano_ppa") }}
            as valor_esperado_3o_ano_ppa,
            {{ parse_financial_value("meta_final_ppa") }} as meta_final_ppa,
            nome_agenda::text as nome_agenda,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "agenda_desagregacao_meta_entrega") }}
    )

select *
from agenda_desagregacao_meta_entrega_raw
