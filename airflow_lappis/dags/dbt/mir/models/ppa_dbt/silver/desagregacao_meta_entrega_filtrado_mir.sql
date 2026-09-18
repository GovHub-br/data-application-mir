{{ config(materialized="table") }}

with
    desagregacao_meta_entrega as (
        select *
        from {{ ref("desagregacao_meta_entrega") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select desagregacao_meta_entrega.*
from desagregacao_meta_entrega
inner join programa_filtrado_mir
    on desagregacao_meta_entrega.programa = programa_filtrado_mir.programa
    and desagregacao_meta_entrega.ano_ppa = programa_filtrado_mir.ano_ppa
