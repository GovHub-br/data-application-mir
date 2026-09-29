-- Falha se alguma fato transacional perder ou duplicar linhas ou valores em
-- relacao a silver de onde vem. A execucao compara com as linhas do nucleo
-- vinculadas a convenios do MIR (convenios de outros orgaos ficam fora).
with
    execucao_silver as (
        select x.*
        from {{ ref("execucao_ne") }} as x
        inner join {{ ref("convenio_mir") }} as c on c.nr_convenio = x.nr_instrumento
        where x.sistema_instrumento = 'SICONV'
    ),

    comparacao as (
        select
            'fato_execucao_orcamentaria' as fato,
            (select count(*) from {{ ref("fato_execucao_orcamentaria") }}) as linhas_fato,
            (select count(*) from execucao_silver) as linhas_silver,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from {{ ref("fato_execucao_orcamentaria") }}
            ) as valor_fato,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from execucao_silver
            ) as valor_silver

        union all

        select
            'fato_fluxo_financeiro',
            (select count(*) from {{ ref("fato_fluxo_financeiro") }}),
            (select count(*) from {{ ref("convenio_movimento_financeiro") }}),
            (select coalesce(sum(valor), 0) from {{ ref("fato_fluxo_financeiro") }}),
            (
                select coalesce(sum(valor), 0)
                from {{ ref("convenio_movimento_financeiro") }}
            )

        union all

        select
            'fato_cronograma_desembolso',
            (select count(*) from {{ ref("fato_cronograma_desembolso") }}),
            (select count(*) from {{ ref("convenio_cronograma") }}),
            (
                select coalesce(sum(valor_previsto), 0)
                from {{ ref("fato_cronograma_desembolso") }}
            ),
            (
                select coalesce(sum(valor_previsto), 0)
                from {{ ref("convenio_cronograma") }}
            )

        union all

        select
            'fato_evento_convenio',
            (select count(*) from {{ ref("fato_evento_convenio") }}),
            (select count(*) from {{ ref("convenio_evento") }}),
            (select coalesce(sum(valor), 0) from {{ ref("fato_evento_convenio") }}),
            (select coalesce(sum(valor), 0) from {{ ref("convenio_evento") }})
    )

select *
from comparacao
where linhas_fato <> linhas_silver or valor_fato <> valor_silver
