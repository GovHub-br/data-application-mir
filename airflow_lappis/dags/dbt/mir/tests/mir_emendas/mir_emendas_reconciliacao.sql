-- Falha se as fatos de Emendas perderem ou duplicarem linhas ou valores em
-- relacao a silver.
with
    comparacao as (
        select
            'fato_execucao_orcamentaria' as fato,
            (
                select count(*) from {{ ref("emendas_fato_execucao_orcamentaria") }}
            ) as linhas_fato,
            (
                select count(*)
                from {{ ref("execucao_ne") }}
                where codigo_emenda is not null
            ) as linhas_silver,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_inscritos), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from {{ ref("emendas_fato_execucao_orcamentaria") }}
            ) as valor_fato,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_inscritos), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from {{ ref("execucao_ne") }}
                where codigo_emenda is not null
            ) as valor_silver

        union all

        select
            'fato_dotacao',
            (select count(*) from {{ ref("emendas_fato_dotacao") }}),
            (select count(*) from {{ ref("emenda_dotacao") }}),
            (
                select
                    coalesce(sum(dotacao_inicial), 0)
                    + coalesce(sum(dotacao_atualizada), 0)
                from {{ ref("emendas_fato_dotacao") }}
            ),
            (
                select
                    coalesce(sum(dotacao_inicial), 0)
                    + coalesce(sum(dotacao_atualizada), 0)
                from {{ ref("emenda_dotacao") }}
            )
    )

select *
from comparacao
where linhas_fato <> linhas_silver or valor_fato <> valor_silver
