{{ config(materialized="table") }}

with
    agenda_entrega as (
        select *
        from {{ ref("agenda_entrega") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select agenda_entrega.*
from agenda_entrega
inner join programa_filtrado_mir
    on agenda_entrega.programa = programa_filtrado_mir.programa
    and agenda_entrega.ano_ppa = programa_filtrado_mir.ano_ppa
