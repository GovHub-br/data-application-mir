{{ config(materialized="table") }}

with
    meta_entrega as (
        select *
        from {{ ref("meta_entrega") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select meta_entrega.*
from meta_entrega
inner join programa_filtrado_mir
    on meta_entrega.programa = programa_filtrado_mir.programa
    and meta_entrega.ano_ppa = programa_filtrado_mir.ano_ppa
