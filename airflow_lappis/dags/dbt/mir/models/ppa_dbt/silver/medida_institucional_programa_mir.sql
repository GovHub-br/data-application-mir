{{ config(materialized="table") }}

with
    medida_institucional_programa as (
        select *
        from {{ ref("medida_institucional_programa") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select medida_institucional_programa.*
from medida_institucional_programa
inner join programa_mir
    on medida_institucional_programa.programa = programa_mir.programa
    and medida_institucional_programa.ano_ppa = programa_mir.ano_ppa
