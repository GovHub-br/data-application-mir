{{ config(materialized="table") }}

with
    objetivo_estrategico_programa as (
        select *
        from {{ ref("objetivo_estrategico_programa") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select objetivo_estrategico_programa.*
from objetivo_estrategico_programa
inner join programa_mir
    on objetivo_estrategico_programa.programa = programa_mir.programa
    and objetivo_estrategico_programa.ano_ppa = programa_mir.ano_ppa
