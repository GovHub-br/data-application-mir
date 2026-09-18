{{ config(materialized="table") }}

with
    indicador_objetivo_especifico as (
        select *
        from {{ ref("indicador_objetivo_especifico") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select indicador_objetivo_especifico.*
from indicador_objetivo_especifico
inner join programa_filtrado_mir
    on indicador_objetivo_especifico.programa = programa_filtrado_mir.programa
    and indicador_objetivo_especifico.ano_ppa = programa_filtrado_mir.ano_ppa
