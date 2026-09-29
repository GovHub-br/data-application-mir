-- Falha se execucao_ne perder, duplicar ou alterar valores em relacao as
-- linhas de empenho do ppa_tesouro (fonte unica da execucao orcamentaria).
with
    fonte as (
        select
            count(*) as linhas,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_liquidadas) as liquidado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos) as rap_inscrito,
            sum(restos_a_pagar_pagos) as rap_pago
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
    ),

    nucleo as (
        select
            count(*) as linhas,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_liquidadas) as liquidado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos) as rap_inscrito,
            sum(restos_a_pagar_pagos) as rap_pago
        from {{ ref("execucao_ne") }}
    )

select f.*, n.*
from fonte as f, nucleo as n
where
    f.linhas <> n.linhas
    or f.empenhado <> n.empenhado
    or f.liquidado <> n.liquidado
    or f.pago <> n.pago
    or f.rap_inscrito <> n.rap_inscrito
    or f.rap_pago <> n.rap_pago
