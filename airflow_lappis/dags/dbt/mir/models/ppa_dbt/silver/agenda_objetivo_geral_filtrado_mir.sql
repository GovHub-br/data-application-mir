{{ config(materialized="table") }}

with
    agenda_objetivo_geral as (
        select *
        from {{ ref("agenda_objetivo_geral") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select agenda_objetivo_geral.*
from agenda_objetivo_geral
inner join programa_filtrado_mir
    on agenda_objetivo_geral.programa = programa_filtrado_mir.programa
    and agenda_objetivo_geral.ano_ppa = programa_filtrado_mir.ano_ppa
