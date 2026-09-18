{{ config(materialized="table") }}

with
    agenda_medida_institucional_programa as (
        select *
        from {{ ref("agenda_medida_institucional_programa") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select agenda_medida_institucional_programa.*
from agenda_medida_institucional_programa
inner join programa_filtrado_mir
    on agenda_medida_institucional_programa.programa = programa_filtrado_mir.programa
    and agenda_medida_institucional_programa.ano_ppa = programa_filtrado_mir.ano_ppa
