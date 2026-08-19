{{ config(materialized="table") }}

with
    objetivo_especifico_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            objetivo::text as objetivo,
            objetivo_especifico::text as objetivo_especifico,
            enunciado::text as enunciado,
            descricao::text as descricao,
            orgao::text as orgao,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "objetivo_especifico") }}
    )

select *
from objetivo_especifico_raw
