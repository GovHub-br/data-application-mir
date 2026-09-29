-- Falha se a posicao de algum plano divergir da soma das fatos do mesmo plano,
-- ou se faltar/sobrar plano.
with
    credito as (
        select
            sk_plano_acao,
            sum(valor) filter (where tipo = 'Recebido') as recebido,
            sum(valor) filter (where tipo = 'Devolvido') as devolvido,
            sum(valor) filter (where tipo = 'Anulado') as anulado
        from {{ ref("teds_fato_credito_descentralizado") }}
        group by sk_plano_acao
    ),

    financeiro as (
        select
            sk_plano_acao,
            sum(valor) filter (where tipo = 'Transferência') as recebido,
            sum(valor) filter (where tipo = 'Devolução') as devolvido
        from {{ ref("teds_fato_programacao_financeira") }}
        group by sk_plano_acao
    ),

    execucao as (
        select
            sk_plano_acao,
            sum(despesas_empenhadas) as empenhado,
            sum(empenhado_bruto) as empenhado_bruto,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos_acumulavel) as rap_inscrito
        from {{ ref("teds_fato_execucao_orcamentaria") }}
        group by sk_plano_acao
    ),

    planos as (
        select sk_plano_acao
        from {{ ref("teds_dim_plano_acao") }}
        where sk_plano_acao <> -1
    )

select coalesce(p.sk_plano_acao, d.sk_plano_acao) as sk_plano_acao
from {{ ref("teds_fato_plano_acao_posicao") }} as p
full join planos as d on d.sk_plano_acao = p.sk_plano_acao
left join credito as c on c.sk_plano_acao = p.sk_plano_acao
left join financeiro as f on f.sk_plano_acao = p.sk_plano_acao
left join execucao as e on e.sk_plano_acao = p.sk_plano_acao
where
    p.sk_plano_acao is null
    or d.sk_plano_acao is null
    or p.credito_recebido <> coalesce(c.recebido, 0)
    or p.credito_devolvido <> coalesce(c.devolvido, 0)
    or p.credito_anulado <> coalesce(c.anulado, 0)
    or p.financeiro_recebido <> coalesce(f.recebido, 0)
    or p.financeiro_devolvido <> coalesce(f.devolvido, 0)
    or coalesce(p.despesas_empenhadas, 0) <> coalesce(e.empenhado, 0)
    or coalesce(p.empenhado_bruto, 0) <> coalesce(e.empenhado_bruto, 0)
    or coalesce(p.despesas_pagas, 0) <> coalesce(e.pago, 0)
    or coalesce(p.restos_a_pagar_inscritos_acumulavel, 0) <> coalesce(e.rap_inscrito, 0)
