{{ config(materialized="table") }}

with
    objetivo_geral as (
        select *
        from {{ ref("objetivo_geral") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select objetivo_geral.*
from objetivo_geral
inner join programa_filtrado_mir
    on objetivo_geral.programa = programa_filtrado_mir.programa
    and objetivo_geral.ano_ppa = programa_filtrado_mir.ano_ppa
