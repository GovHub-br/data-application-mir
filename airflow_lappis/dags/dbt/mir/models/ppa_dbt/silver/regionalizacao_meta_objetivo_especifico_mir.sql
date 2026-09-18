{{ config(materialized="table") }}

with
    regionalizacao_meta_objetivo_especifico as (
        select *
        from {{ ref("regionalizacao_meta_objetivo_especifico") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select regionalizacao_meta_objetivo_especifico.*
from regionalizacao_meta_objetivo_especifico
inner join programa_mir
    on regionalizacao_meta_objetivo_especifico.programa = programa_mir.programa
    and regionalizacao_meta_objetivo_especifico.ano_ppa = programa_mir.ano_ppa
