{{ config(materialized="table") }}

with
    agenda_medida_institucional_objetivo_especifico as (
        select *
        from {{ ref("agenda_medida_institucional_objetivo_especifico") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select agenda_medida_institucional_objetivo_especifico.*
from agenda_medida_institucional_objetivo_especifico
inner join programa_mir
    on agenda_medida_institucional_objetivo_especifico.programa = programa_mir.programa
    and agenda_medida_institucional_objetivo_especifico.ano_ppa = programa_mir.ano_ppa
