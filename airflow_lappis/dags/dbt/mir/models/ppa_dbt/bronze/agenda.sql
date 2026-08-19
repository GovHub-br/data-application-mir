{{ config(materialized="table") }}

with
    agenda_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            codigo::text as codigo,
            titulo::text as titulo,
            descricao::text as descricao,
            tipo::text as tipo,
            nome::text as nome,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "agenda") }}
    )

select *
from agenda_raw
