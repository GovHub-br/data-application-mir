{{ config(materialized="table") }}

with
    indicador_entrega as (
        select *
        from {{ ref("indicador_entrega") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select indicador_entrega.*
from indicador_entrega
inner join programa_mir
    on indicador_entrega.programa = programa_mir.programa
    and indicador_entrega.ano_ppa = programa_mir.ano_ppa
