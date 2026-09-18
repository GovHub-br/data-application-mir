{{ config(materialized="table") }}

with
    meta_objetivo_especifico as (
        select *
        from {{ ref("meta_objetivo_especifico") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select meta_objetivo_especifico.*
from meta_objetivo_especifico
inner join programa_mir
    on meta_objetivo_especifico.programa = programa_mir.programa
    and meta_objetivo_especifico.ano_ppa = programa_mir.ano_ppa
