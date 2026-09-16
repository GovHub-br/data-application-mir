{{ config(materialized="table") }}

with
    acao as (
        select *
        from {{ ref("acao_nao_orcamentaria") }}
    ),
    programa_mir as (
        select programa, ano_ppa
        from {{ ref("programa_mir") }}
    )

select acao.*
from acao
inner join programa_mir
    on acao.programa = programa_mir.programa
    and acao.ano_ppa = programa_mir.ano_ppa
