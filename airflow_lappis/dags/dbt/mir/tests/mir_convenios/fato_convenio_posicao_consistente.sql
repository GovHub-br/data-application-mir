-- Falha se a posicao de algum convenio divergir da soma das fatos
-- transacionais do mesmo convenio, ou se faltar/sobrar convenio.
with
    fluxo as (
        select
            sk_convenio,
            sum(valor) filter (
                where tipo_movimento = 'Desembolso federal'
            ) as desembolsado,
            count(*) filter (
                where tipo_movimento = 'Desembolso federal'
            ) as qtd_desembolsos,
            sum(valor) filter (
                where tipo_movimento = 'Pagamento a fornecedor'
            ) as pago_fornecedores,
            sum(valor) filter (where tipo_movimento = 'Pagamento de tributo') as tributos
        from {{ ref("fato_fluxo_financeiro") }}
        group by sk_convenio
    ),

    execucao as (
        select
            sk_convenio,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos_acumulavel) as rap_inscrito
        from {{ ref("fato_execucao_orcamentaria") }}
        group by sk_convenio
    ),

    eventos as (
        select
            sk_convenio,
            count(*) filter (where tipo_evento = 'Termo aditivo') as qtd_aditivos
        from {{ ref("fato_evento_convenio") }}
        group by sk_convenio
    ),

    convenios as (
        select sk_convenio from {{ ref("dim_convenio") }} where sk_convenio <> -1
    )

select coalesce(p.sk_convenio, c.sk_convenio) as sk_convenio
from {{ ref("fato_convenio_posicao") }} as p
full join convenios as c on c.sk_convenio = p.sk_convenio
left join fluxo as f on f.sk_convenio = p.sk_convenio
left join execucao as e on e.sk_convenio = p.sk_convenio
left join eventos as v on v.sk_convenio = p.sk_convenio
where
    p.sk_convenio is null
    or c.sk_convenio is null
    or p.valor_desembolsado <> coalesce(f.desembolsado, 0)
    or p.qtd_desembolsos <> coalesce(f.qtd_desembolsos, 0)
    or p.valor_pago_fornecedores <> coalesce(f.pago_fornecedores, 0)
    or p.valor_tributos <> coalesce(f.tributos, 0)
    or coalesce(p.despesas_empenhadas, 0) <> coalesce(e.empenhado, 0)
    or coalesce(p.despesas_pagas, 0) <> coalesce(e.pago, 0)
    or coalesce(p.restos_a_pagar_inscritos_acumulavel, 0) <> coalesce(e.rap_inscrito, 0)
    or p.qtd_aditivos <> coalesce(v.qtd_aditivos, 0)
