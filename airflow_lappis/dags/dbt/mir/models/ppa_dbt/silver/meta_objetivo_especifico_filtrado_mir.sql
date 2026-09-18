{{ config(materialized="table") }}

with
    meta_objetivo_especifico as (
        select *
        from {{ ref("meta_objetivo_especifico") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select meta_objetivo_especifico.*
from meta_objetivo_especifico
inner join programa_filtrado_mir
    on meta_objetivo_especifico.programa = programa_filtrado_mir.programa
    and meta_objetivo_especifico.ano_ppa = programa_filtrado_mir.ano_ppa
