{{ config(materialized="table") }}

with
    objetivo_estrategico_programa_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            objetivo_estrategico::text as objetivo_estrategico,
            titulo_objetivo_estrategico::text as titulo_objetivo_estrategico,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "objetivo_estrategico_programa") }}
    )

select *
from objetivo_estrategico_programa_raw
