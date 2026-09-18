{{ config(materialized="table") }}

with
    regionalizacao_meta_entrega as (
        select *
        from {{ ref("regionalizacao_meta_entrega") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select regionalizacao_meta_entrega.*
from regionalizacao_meta_entrega
inner join programa_mir
    on regionalizacao_meta_entrega.programa = programa_mir.programa
    and regionalizacao_meta_entrega.ano_ppa = programa_mir.ano_ppa
