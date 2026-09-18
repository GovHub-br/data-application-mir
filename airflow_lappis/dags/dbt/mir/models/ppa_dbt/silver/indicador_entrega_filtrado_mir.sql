{{ config(materialized="table") }}

with
    indicador_entrega as (
        select *
        from {{ ref("indicador_entrega") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select indicador_entrega.*
from indicador_entrega
inner join programa_filtrado_mir
    on indicador_entrega.programa = programa_filtrado_mir.programa
    and indicador_entrega.ano_ppa = programa_filtrado_mir.ano_ppa
