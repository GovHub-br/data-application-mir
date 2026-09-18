{{ config(materialized="table") }}

with
    indicador_objetivo_especifico as (
        select *
        from {{ ref("indicador_objetivo_especifico") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select indicador_objetivo_especifico.*
from indicador_objetivo_especifico
inner join programa_mir
    on indicador_objetivo_especifico.programa = programa_mir.programa
    and indicador_objetivo_especifico.ano_ppa = programa_mir.ano_ppa
