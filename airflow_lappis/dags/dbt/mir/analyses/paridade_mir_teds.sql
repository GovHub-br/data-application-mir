-- Paridade temporaria (spec §11): posicao nova x ted_resumo_orcamentario, plano
-- a plano e medida a medida. Apagar na etapa 5, junto com o gold antigo.
-- O resumo antigo esta no grao do num_transf; so as linhas com plano entram
-- (as 245 sem plano sao, em 234 casos, convenios contados como TED).
-- Diferencas aceitas: ver a Tarefa 7 do plano da etapa 3.
with
    antigo as (
        select * from {{ ref("ted_resumo_orcamentario") }} where plano_acao is not null
    ),

    novo as (
        select d.id_plano_acao, p.*
        from {{ ref("teds_fato_plano_acao_posicao") }} as p
        inner join
            {{ ref("teds_dim_plano_acao") }} as d on d.sk_plano_acao = p.sk_plano_acao
    ),

    pares as (
        select
            coalesce(a.plano_acao, n.id_plano_acao) as id_plano_acao,
            a.plano_acao is not null as tem_antigo,
            n.id_plano_acao is not null as tem_novo,
            a,
            n
        from antigo as a
        full join novo as n on n.id_plano_acao = a.plano_acao
    )

select p.id_plano_acao, c.medida, c.valor_antigo, c.valor_novo
from pares as p
cross join
    lateral(
        values
            (
                'presenca',
                p.tem_antigo::text,
                p.tem_novo::text,
                not (p.tem_antigo and p.tem_novo)
            ),
            (
                'valor_firmado',
                (p.a).valor_firmado::text,
                (p.n).valor_firmado::text,
                coalesce((p.a).valor_firmado, 0) <> coalesce((p.n).valor_firmado, 0)
            ),
            (
                'empenhado_bruto',
                (p.a).empenhado::text,
                (p.n).empenhado_bruto::text,
                coalesce((p.a).empenhado, 0) <> coalesce((p.n).empenhado_bruto, 0)
            ),
            (
                'empenho_anulado',
                (p.a).empenho_anulado::text,
                (p.n).empenho_anulado::text,
                coalesce((p.a).empenho_anulado, 0) <> coalesce((p.n).empenho_anulado, 0)
            ),
            (
                'liquidado',
                (p.a).despesas_liquidada::text,
                (p.n).despesas_liquidadas::text,
                coalesce((p.a).despesas_liquidada, 0)
                <> coalesce((p.n).despesas_liquidadas, 0)
            ),
            (
                'pago_exercicio',
                (p.a).despesas_pagas_exercicio::text,
                (p.n).despesas_pagas::text,
                coalesce((p.a).despesas_pagas_exercicio, 0)
                <> coalesce((p.n).despesas_pagas, 0)
            ),
            (
                'rap_pago',
                (p.a).despesas_pagas_rap::text,
                (p.n).restos_a_pagar_pagos::text,
                coalesce((p.a).despesas_pagas_rap, 0)
                <> coalesce((p.n).restos_a_pagar_pagos, 0)
            ),
            (
                'rap_inscrito',
                (p.a).restos_a_pagar::text,
                (p.n).restos_a_pagar_inscritos_acumulavel::text,
                coalesce((p.a).restos_a_pagar, 0)
                <> coalesce((p.n).restos_a_pagar_inscritos_acumulavel, 0)
            ),
            (
                'credito_recebido',
                (p.a).orcamento_recebido::text,
                (p.n).credito_recebido::text,
                coalesce((p.a).orcamento_recebido, 0)
                <> coalesce((p.n).credito_recebido, 0)
            ),
            (
                'credito_devolvido',
                (p.a).orcamento_devolvido::text,
                (p.n).credito_devolvido::text,
                coalesce((p.a).orcamento_devolvido, 0)
                <> coalesce((p.n).credito_devolvido, 0)
            ),
            (
                'financeiro_recebido',
                (p.a).financeiro_recebido::text,
                (p.n).financeiro_recebido::text,
                coalesce((p.a).financeiro_recebido, 0)
                <> coalesce((p.n).financeiro_recebido, 0)
            ),
            (
                'financeiro_devolvido',
                (p.a).financeiro_devolvido::text,
                (p.n).financeiro_devolvido::text,
                coalesce((p.a).financeiro_devolvido, 0)
                <> coalesce((p.n).financeiro_devolvido, 0)
            )
    ) as c(medida, valor_antigo, valor_novo, difere)
-- As medidas so sao comparadas nos planos presentes nos dois lados
where c.difere and (c.medida = 'presenca' or (p.tem_antigo and p.tem_novo))
