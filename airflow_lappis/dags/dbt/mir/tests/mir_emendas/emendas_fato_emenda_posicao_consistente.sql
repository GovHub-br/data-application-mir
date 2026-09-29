-- Falha se a posicao de alguma emenda divergir da soma das fatos, ou se
-- faltar/sobrar emenda.
with
    dotacao as (
        select
            sk_emenda,
            sum(dotacao_inicial) as inicial,
            sum(dotacao_atualizada) as atualizada
        from {{ ref("emendas_fato_dotacao") }}
        group by sk_emenda
    ),

    execucao as (
        select
            sk_emenda,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_liquidadas) as liquidado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos_acumulavel) as rap_inscrito,
            sum(restos_a_pagar_pagos) as rap_pago,
            count(distinct ne_ccor) as qtd_nes
        from {{ ref("emendas_fato_execucao_orcamentaria") }}
        group by sk_emenda
    ),

    emendas as (
        select sk_emenda
        from dotacao
        union
        select sk_emenda
        from execucao
    )

select coalesce(p.sk_emenda, e.sk_emenda) as sk_emenda
from {{ ref("emendas_fato_emenda_posicao") }} as p
full join emendas as e on e.sk_emenda = p.sk_emenda
left join dotacao as d on d.sk_emenda = p.sk_emenda
left join execucao as x on x.sk_emenda = p.sk_emenda
where
    p.sk_emenda is null
    or e.sk_emenda is null
    or p.dotacao_inicial <> coalesce(d.inicial, 0)
    or p.dotacao_atualizada <> coalesce(d.atualizada, 0)
    or p.despesas_empenhadas <> coalesce(x.empenhado, 0)
    or p.despesas_liquidadas <> coalesce(x.liquidado, 0)
    or p.despesas_pagas <> coalesce(x.pago, 0)
    or p.restos_a_pagar_inscritos_acumulavel <> coalesce(x.rap_inscrito, 0)
    or p.restos_a_pagar_pagos <> coalesce(x.rap_pago, 0)
    or p.qtd_nes <> coalesce(x.qtd_nes, 0)
