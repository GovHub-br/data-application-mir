-- Avisa quando as NEs não reproduzem, célula a célula, a consulta oficial "Execução TED
-- por UG" (empenhado, liquidado e pago). A atribuição por instrumento só fecha com o
-- oficial se a base de NEs fechar. É aviso, não erro: a diferença vem da extração, não do
-- código. Causas conhecidas: o relatório de NEs em "Moeda Origem" (a UG 364150 do CNPq
-- paga em dólar) e as duas consultas extraídas em datas diferentes (ver a var
-- ted_execucao_corte_emissao em execucao_ted_ne).
{{ config(severity="warn") }}

with
    oficial as (
        select
            ano_lancamento as ano,
            ug_executora_codigo as ug,
            acao_governo_codigo as acao,
            plano_orcamentario_codigo as po,
            ptres,
            grupo_despesa as grupo,
            fonte_recursos_detalhada as fonte,
            despesas_empenhadas as emp,
            despesas_liquidadas as liq,
            despesas_pagas as pag
        from {{ ref("execucao_ted_ug") }}
    ),

    ne as (
        select ano, ug, acao, po, ptres, grupo, fonte, sum(emp) as emp, sum(liq) as liq, sum(pag) as pag
        from {{ ref("execucao_ted_ne") }}
        where ug in (select ug from oficial)
        group by ano, ug, acao, po, ptres, grupo, fonte
    )

select
    coalesce(o.ano, n.ano) as ano,
    coalesce(o.ug, n.ug) as ug,
    coalesce(o.acao, n.acao) as acao,
    coalesce(o.po, n.po) as po,
    coalesce(o.ptres, n.ptres) as ptres,
    coalesce(o.grupo, n.grupo) as grupo,
    coalesce(o.fonte, n.fonte) as fonte,
    o.emp as emp_oficial,
    n.emp as emp_ne,
    o.liq as liq_oficial,
    n.liq as liq_ne,
    o.pag as pag_oficial,
    n.pag as pag_ne
from oficial as o
full join ne as n using (ano, ug, acao, po, ptres, grupo, fonte)
where
    abs(coalesce(o.emp, 0) - coalesce(n.emp, 0)) >= 0.01
    or abs(coalesce(o.liq, 0) - coalesce(n.liq, 0)) >= 0.01
    or abs(coalesce(o.pag, 0) - coalesce(n.pag, 0)) >= 0.01
