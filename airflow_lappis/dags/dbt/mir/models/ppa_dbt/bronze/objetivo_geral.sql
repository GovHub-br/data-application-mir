{{ config(materialized="table") }}

with
    objetivo_geral_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            objetivo::text as objetivo,
            enunciado::text as enunciado,
            descricao::text as descricao,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "objetivo_geral") }}
    )

select *
from objetivo_geral_raw
