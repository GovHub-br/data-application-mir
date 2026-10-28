-- Falha se a execução por instrumento perder ou duplicar valor: por ano, o empenhado,
-- liquidado, pago e restos a pagar da gold têm de ser os das NEs da consulta oficial
-- (execucao_ted_ne).
-- Nada é rateado, então a abertura por instrumento só redistribui o total do ano.
with
    gold as (
        select
            ano,
            sum(empenhado) as emp,
            sum(liquidado) as liq,
            sum(pago) as pag,
            sum(rap_inscrito) as insc_rap,
            sum(pago_rap) as pag_rap,
            sum(rap_a_pagar) as saldo_rap
        from {{ ref("ted_execucao_por_instrumento") }}
        group by ano
    ),

    fonte as (
        select
            ano,
            sum(emp) as emp,
            sum(liq) as liq,
            sum(pag) as pag,
            sum(insc_rap) as insc_rap,
            sum(pag_rap) as pag_rap,
            sum(saldo_rap) as saldo_rap
        from {{ ref("execucao_ted_ne") }}
        where oficial
        group by ano
    )

select coalesce(g.ano, f.ano) as ano, g.emp as emp_gold, f.emp as emp_fonte, g.liq as liq_gold, f.liq as liq_fonte, g.pag as pag_gold, f.pag as pag_fonte, g.pag_rap as pag_rap_gold, f.pag_rap as pag_rap_fonte, g.insc_rap as insc_rap_gold, f.insc_rap as insc_rap_fonte, g.saldo_rap as saldo_rap_gold, f.saldo_rap as saldo_rap_fonte
from gold as g
full join fonte as f on f.ano = g.ano
where
    round(coalesce(g.emp, 0), 2) <> round(coalesce(f.emp, 0), 2)
    or round(coalesce(g.liq, 0), 2) <> round(coalesce(f.liq, 0), 2)
    or round(coalesce(g.pag, 0), 2) <> round(coalesce(f.pag, 0), 2)
    or round(coalesce(g.insc_rap, 0), 2) <> round(coalesce(f.insc_rap, 0), 2)
    or round(coalesce(g.pag_rap, 0), 2) <> round(coalesce(f.pag_rap, 0), 2)
    or round(coalesce(g.saldo_rap, 0), 2) <> round(coalesce(f.saldo_rap, 0), 2)
