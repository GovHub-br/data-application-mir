{{ config(materialized="table") }}

{#
  Base de NEs da execução dos TEDs por instrumento (analises/ted_execucao/pipeline.py,
  seção "base"): as NEs de ppa_tesouro recortadas como a consulta oficial "Execução TED
  por UG" (execucao_ted_ug): resultado EOF 2, sem as UGs e ações que a consulta não traz.

  Grão: uma linha por NE (cada NE cai numa única célula ano x UG x ação x PO x PTRES x
  grupo x fonte). `oficial` marca a NE cuja célula está na consulta oficial; só essas são
  atribuídas a instrumento, mas todas entram nas regras de texto (propagação por NE de
  referência, processo e contrato).

  texto = descrição | informações complementares | observações, em maiúsculas, como no
  Python. Diferença deliberada: o Python pega a informação complementar da PRIMEIRA linha
  da NE, e o relatório repete a NE com "NAO SE APLICA" em parte das linhas, então o número
  do TED citado ali dependia da ordem do CSV. Aqui entram todos os valores distintos.

  Restos a pagar: o exercício de cada linha é o ano no fim de emissao_mes ("000/2026" na
  inscrição), como na DAG do PPA. A NE não paga é reinscrita a cada exercício, então o
  RAP inscrito não se soma entre exercícios:
  - insc_rap: inscrito no exercício seguinte ao da NE, o que passou para restos a pagar;
  - pag_rap: restos a pagar pagos, somados em todos os exercícios seguintes;
  - saldo_rap: inscrito menos pago no último exercício do relatório, o que falta pagar
    (o relatório não traz o RAP cancelado durante esse exercício).

  A var `ted_execucao_corte_emissao` (YYYY-MM-DD) corta as NEs emitidas depois da data de
  posição da consulta oficial, quando as duas extrações não são do mesmo dia.
#}
with
    orgao_da_ug as (
        select ug_executora_codigo as ug, min(orgao_uge_codigo) as orgao
        from {{ ref("execucao_ted_ug") }}
        group by ug_executora_codigo
    ),

    celulas_oficiais as (
        select distinct
            ano_lancamento as ano,
            ug_executora_codigo as ug,
            acao_governo_codigo as acao,
            plano_orcamentario_codigo as po,
            ptres,
            grupo_despesa as grupo,
            fonte_recursos_detalhada as fonte
        from {{ ref("execucao_ted_ug") }}
    ),

    linhas as (
        select
            ne_ccor,
            ne_ccor_ano_emissao as ano,
            left(ne_ccor, 6) as ug,
            acao_governo as acao,
            plano_orcamentario_codigo_po as po,
            ptres,
            grupo_despesa::text as grupo,
            fonte_recursos_detalhada as fonte,
            despesas_empenhadas as emp,
            despesas_liquidadas as liq,
            despesas_pagas as pag,
            right(emissao_mes, 4)::integer as exercicio,
            max(right(emissao_mes, 4)::integer) over () as ultimo_exercicio,
            restos_a_pagar_inscritos as insc_rap,
            restos_a_pagar_pagos as pag_rap,
            ne_ccor_descricao,
            coalesce(ne_info_complementar, '') as info,
            coalesce(doc_observacao, '') as doc,
            regexp_replace(coalesce(ne_num_processo, ''), '\D', '', 'g') as processo,
            ne_ccor_favorecido_descricao,
            natureza_despesa,
            natureza_despesa_descricao,
            fonte_recursos_detalhada_descricao
        from {{ ref("ppa_tesouro") }}
        where
            ne_ccor <> '-9'
            and resultado_eof_codigo = 2
            and left(ne_ccor, 6) not in {{ ted_execucao_ugs_excluidas() }}
            and upper(acao_governo) not in {{ ted_execucao_acoes_excluidas() }}
            {% if var("ted_execucao_corte_emissao", none) %}
            and (
                ne_ccor_ano_emissao < {{ var("ted_execucao_corte_emissao")[:4] }}
                or to_date(emissao_dia, 'DD/MM/YYYY')
                <= '{{ var("ted_execucao_corte_emissao") }}'::date
                or emissao_dia is null
            )
            {% endif %}
    ),

    -- valores distintos por NE, em ordem de ponto de código (como o sorted() do Python)
    infos as (
        select ne_ccor, string_agg(info, ' | ' order by info collate "C") as info
        from (select distinct ne_ccor, info from linhas) as d
        group by ne_ccor
    ),

    docs as (
        select ne_ccor, string_agg(doc, ' | ' order by doc collate "C") as docs
        from (select distinct ne_ccor, doc from linhas) as d
        group by ne_ccor
    ),

    por_ne as (
        select
            ne_ccor,
            ano,
            ug,
            acao,
            po,
            ptres,
            grupo,
            fonte,
            sum(emp) as emp,
            sum(liq) as liq,
            sum(pag) as pag,
            coalesce(sum(insc_rap) filter (where exercicio = ano + 1), 0) as insc_rap,
            coalesce(sum(pag_rap), 0) as pag_rap,
            coalesce(
                sum(insc_rap - pag_rap)
                filter (where exercicio = ultimo_exercicio and exercicio > ano),
                0
            ) as saldo_rap,
            -- o Python escolhe as NEs a atribuir pela linha com valor, não pela soma
            bool_or(abs(emp) > 0.005 or abs(liq) > 0.005 or abs(pag) > 0.005) as tem_movimento,
            min(ne_ccor_descricao) as ne_ccor_descricao,
            -- primeiro processo informado (o -9 vira 9 e cai no corte de 15 dígitos)
            min(processo) filter (where length(processo) >= 15) as processo,
            min(ne_ccor_favorecido_descricao) as favorecido,
            -- a natureza é do cabeçalho da NE: um valor só por NE
            min(natureza_despesa) as natureza_despesa,
            min(natureza_despesa_descricao) as natureza_despesa_descricao,
            min(fonte_recursos_detalhada_descricao) as fonte_descricao
        from linhas
        group by ne_ccor, ano, ug, acao, po, ptres, grupo, fonte
    )

select
    n.ne_ccor,
    n.ano,
    n.ug,
    o.orgao as orgao_ug,
    n.acao,
    n.po,
    n.ptres,
    n.grupo,
    n.fonte,
    concat_ws('|', n.ano, o.orgao, n.ptres, n.fonte) as celula_credito,
    c.ano is not null as oficial,
    n.emp,
    n.liq,
    n.pag,
    n.insc_rap,
    n.pag_rap,
    n.saldo_rap,
    n.tem_movimento,
    n.ne_ccor_descricao,
    n.processo,
    n.favorecido,
    n.natureza_despesa,
    n.natureza_despesa_descricao,
    n.fonte_descricao,
    upper(
        concat_ws(' | ', coalesce(n.ne_ccor_descricao, ''), i.info, d.docs)
    ) as texto
from por_ne as n
left join orgao_da_ug as o on o.ug = n.ug
left join
    celulas_oficiais as c
    on c.ano = n.ano
    and c.ug = n.ug
    and c.acao = n.acao
    and c.po = n.po
    and c.ptres = n.ptres
    and c.grupo = n.grupo
    and c.fonte = n.fonte
left join infos as i on i.ne_ccor = n.ne_ccor
left join docs as d on d.ne_ccor = n.ne_ccor
