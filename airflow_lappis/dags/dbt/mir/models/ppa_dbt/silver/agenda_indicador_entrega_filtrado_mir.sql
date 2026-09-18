{{ config(materialized="table") }}

with
    agenda_indicador_entrega as (
        select *
        from {{ ref("agenda_indicador_entrega") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select agenda_indicador_entrega.*
from agenda_indicador_entrega
inner join programa_filtrado_mir
    on agenda_indicador_entrega.programa = programa_filtrado_mir.programa
    and agenda_indicador_entrega.ano_ppa = programa_filtrado_mir.ano_ppa
