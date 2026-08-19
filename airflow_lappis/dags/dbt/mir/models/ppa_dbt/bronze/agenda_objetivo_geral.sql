{{ config(materialized="table") }}

with
    agenda_objetivo_geral_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            codigo_agenda::text as codigo_agenda,
            programa::text as programa,
            objetivo::text as objetivo,
            enunciado::text as enunciado,
            descricao::text as descricao,
            nome_agenda::text as nome_agenda,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "agenda_objetivo_geral") }}
    )

select *
from agenda_objetivo_geral_raw
