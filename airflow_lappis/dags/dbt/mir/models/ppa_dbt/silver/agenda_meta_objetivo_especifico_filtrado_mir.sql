{{ config(materialized="table") }}

with
    agenda_meta_objetivo_especifico as (
        select *
        from {{ ref("agenda_meta_objetivo_especifico") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select agenda_meta_objetivo_especifico.*
from agenda_meta_objetivo_especifico
inner join programa_filtrado_mir
    on agenda_meta_objetivo_especifico.programa = programa_filtrado_mir.programa
    and agenda_meta_objetivo_especifico.ano_ppa = programa_filtrado_mir.ano_ppa
