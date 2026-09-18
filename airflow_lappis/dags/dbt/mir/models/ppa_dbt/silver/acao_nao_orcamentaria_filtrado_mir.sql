{{ config(materialized="table") }}

with
    acao as (
        select *
        from {{ ref("acao_nao_orcamentaria") }}
    ),
    programa_filtrado_mir as (
        select programa, ano_ppa
        from {{ ref("programa_filtrado_mir") }}
    )

select acao.*
from acao
inner join programa_filtrado_mir
    on acao.programa = programa_filtrado_mir.programa
    and acao.ano_ppa = programa_filtrado_mir.ano_ppa
