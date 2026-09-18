{{ config(materialized="table") }}

with
    desagregacao_meta_objetivo_especifico as (
        select *
        from {{ ref("desagregacao_meta_objetivo_especifico") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select desagregacao_meta_objetivo_especifico.*
from desagregacao_meta_objetivo_especifico
inner join programa_filtrado_mir
    on desagregacao_meta_objetivo_especifico.programa = programa_filtrado_mir.programa
    and desagregacao_meta_objetivo_especifico.ano_ppa = programa_filtrado_mir.ano_ppa
