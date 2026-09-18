{{ config(materialized="table") }}

with
    agenda as (
        select *
        from {{ ref("agenda") }}
    ),
    agenda_programa_mir as (
        select distinct codigo_agenda, ano_ppa
        from {{ ref("agenda_programa_mir") }}
    )

select agenda.*
from agenda
inner join agenda_programa_mir
    on agenda.codigo = agenda_programa_mir.codigo_agenda
    and agenda.ano_ppa = agenda_programa_mir.ano_ppa
