-- Falha se alguma fato perder ou duplicar linhas ou valores em relacao a
-- silver de onde vem. A execucao compara com as linhas do nucleo ligadas a um
-- plano de TED.
with
    execucao_silver as (
        select x.* from {{ ref("execucao_ne") }} as x where x.sistema_instrumento = 'TED'
    ),

    comparacao as (
        select
            'fato_credito_descentralizado' as fato,
            (
                select count(*) from {{ ref("teds_fato_credito_descentralizado") }}
            ) as linhas_fato,
            (select count(*) from {{ ref("ted_credito_nc") }}) as linhas_silver,
            (
                select coalesce(sum(valor), 0)
                from {{ ref("teds_fato_credito_descentralizado") }}
            ) as valor_fato,
            (
                select coalesce(sum(valor), 0) from {{ ref("ted_credito_nc") }}
            ) as valor_silver

        union all

        select
            'fato_programacao_financeira',
            (select count(*) from {{ ref("teds_fato_programacao_financeira") }}),
            (select count(*) from {{ ref("ted_programacao_pf") }}),
            (
                select coalesce(sum(valor), 0)
                from {{ ref("teds_fato_programacao_financeira") }}
            ),
            (select coalesce(sum(valor), 0) from {{ ref("ted_programacao_pf") }})

        union all

        select
            'fato_execucao_orcamentaria',
            (select count(*) from {{ ref("teds_fato_execucao_orcamentaria") }}),
            (select count(*) from execucao_silver),
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_inscritos), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from {{ ref("teds_fato_execucao_orcamentaria") }}
            ),
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_inscritos), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from execucao_silver
            )
    )

select *
from comparacao
where linhas_fato <> linhas_silver or valor_fato <> valor_silver
