{{ config(materialized="table") }}

with
    entrega as (
        select *
        from {{ ref("entrega") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select entrega.*
from entrega
inner join programa_mir
    on entrega.programa = programa_mir.programa
    and entrega.ano_ppa = programa_mir.ano_ppa
