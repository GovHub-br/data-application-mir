{{ config(materialized="table") }}

with
    agenda_regionalizacao_meta_entrega as (
        select *
        from {{ ref("agenda_regionalizacao_meta_entrega") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select agenda_regionalizacao_meta_entrega.*
from agenda_regionalizacao_meta_entrega
inner join programa_mir
    on agenda_regionalizacao_meta_entrega.programa = programa_mir.programa
    and agenda_regionalizacao_meta_entrega.ano_ppa = programa_mir.ano_ppa
