{{ config(materialized="table") }}

with
    medida_institucional_programa_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            descricao::text as descricao,
            enunciado::text as enunciado,
            unidade_responsavel::text as unidade_responsavel,
            resultados_esperados::text as resultados_esperados,
            prioritaria::text as prioritaria,
            pac::text as pac,
            medida_institucional_normativa::text as medida_institucional_normativa,
            orgao_responsavel::text as orgao_responsavel,
            concluida::text as concluida,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "medida_institucional_programa") }}
    )

select *
from medida_institucional_programa_raw
