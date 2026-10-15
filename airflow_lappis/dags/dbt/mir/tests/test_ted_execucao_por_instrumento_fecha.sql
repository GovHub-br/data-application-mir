-- Falha se a execução por instrumento perder ou duplicar valor: por ano, o empenhado,
-- liquidado e pago da gold têm de ser os das NEs da consulta oficial (execucao_ted_ne).
-- Nada é rateado, então a abertura por instrumento só redistribui o total do ano.
with
    gold as (
        select ano, sum(empenhado) as emp, sum(liquidado) as liq, sum(pago) as pag
        from {{ ref("ted_execucao_por_instrumento") }}
        group by ano
    ),

    fonte as (
        select ano, sum(emp) as emp, sum(liq) as liq, sum(pag) as pag
        from {{ ref("execucao_ted_ne") }}
        where oficial
        group by ano
    )

select coalesce(g.ano, f.ano) as ano, g.emp as emp_gold, f.emp as emp_fonte, g.liq as liq_gold, f.liq as liq_fonte, g.pag as pag_gold, f.pag as pag_fonte
from gold as g
full join fonte as f on f.ano = g.ano
where
    round(coalesce(g.emp, 0), 2) <> round(coalesce(f.emp, 0), 2)
    or round(coalesce(g.liq, 0), 2) <> round(coalesce(f.liq, 0), 2)
    or round(coalesce(g.pag, 0), 2) <> round(coalesce(f.pag, 0), 2)
