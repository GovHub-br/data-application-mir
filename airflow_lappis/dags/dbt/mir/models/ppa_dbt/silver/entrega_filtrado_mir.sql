{{ config(materialized="table") }}

with
    entrega as (
        select *
        from {{ ref("entrega") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select entrega.*
from entrega
inner join programa_filtrado_mir
    on entrega.programa = programa_filtrado_mir.programa
    and entrega.ano_ppa = programa_filtrado_mir.ano_ppa
