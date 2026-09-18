{{ config(materialized="table") }}

with
    medida_institucional_objetivo_especifico as (
        select *
        from {{ ref("medida_institucional_objetivo_especifico") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select medida_institucional_objetivo_especifico.*
from medida_institucional_objetivo_especifico
inner join programa_mir
    on medida_institucional_objetivo_especifico.programa = programa_mir.programa
    and medida_institucional_objetivo_especifico.ano_ppa = programa_mir.ano_ppa
