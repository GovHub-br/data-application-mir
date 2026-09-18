{{ config(materialized="table") }}

with
    agenda_programa as (
        select *
        from {{ ref("agenda_programa") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select agenda_programa.*
from agenda_programa
inner join programa_filtrado_mir
    on agenda_programa.programa = programa_filtrado_mir.programa
    and agenda_programa.ano_ppa = programa_filtrado_mir.ano_ppa
