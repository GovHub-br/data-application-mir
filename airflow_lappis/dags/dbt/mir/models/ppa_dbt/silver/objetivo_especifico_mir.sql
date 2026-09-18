{{ config(materialized="table") }}

with
    objetivo_especifico as (
        select *
        from {{ ref("objetivo_especifico") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select objetivo_especifico.*
from objetivo_especifico
inner join programa_mir
    on objetivo_especifico.programa = programa_mir.programa
    and objetivo_especifico.ano_ppa = programa_mir.ano_ppa
