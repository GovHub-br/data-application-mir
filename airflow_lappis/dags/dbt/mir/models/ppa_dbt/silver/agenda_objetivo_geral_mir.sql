{{ config(materialized="table") }}

with
    agenda_objetivo_geral as (
        select *
        from {{ ref("agenda_objetivo_geral") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select agenda_objetivo_geral.*
from agenda_objetivo_geral
inner join programa_mir
    on agenda_objetivo_geral.programa = programa_mir.programa
    and agenda_objetivo_geral.ano_ppa = programa_mir.ano_ppa
