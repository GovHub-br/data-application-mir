{{ config(materialized="table") }}

with
    agenda_medida_institucional_objetivo_especifico_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            codigo_agenda::text as codigo_agenda,
            programa::text as programa,
            objetivo_geral::text as objetivo_geral,
            objetivo_especifico::text as objetivo_especifico,
            descricao::text as descricao,
            enunciado::text as enunciado,
            unidade_responsavel::text as unidade_responsavel,
            resultados_esperados::text as resultados_esperados,
            prioritaria::text as prioritaria,
            pac::text as pac,
            nome_agenda::text as nome_agenda,
            objetivo::text as objetivo,
            medida_institucional_normativa::text as medida_institucional_normativa,
            orgao_responsavel::text as orgao_responsavel,
            concluida::text as concluida,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "agenda_medida_institucional_objetivo_especifico") }}
    )

select *
from agenda_medida_institucional_objetivo_especifico_raw
