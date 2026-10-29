{{ config(materialized="table") }}

{#
  Execução dos TEDs do MIR por instrumento: a consulta oficial "Execução TED por UG" aberta
  por TED ou tedinho (analises/ted_execucao/pipeline.py, saida/execucao_por_ted.csv).

  Grão: ano x instrumento. O que nenhuma regra resolveu fica em '(não identificado)', no
  ano, sem rateio; assim a soma por ano reproduz o empenhado, liquidado e pago das NEs da
  consulta oficial (teste test_ted_execucao_por_instrumento_fecha).

  empenhado_<camada>: parte do empenhado que veio de cada camada de identificação
  (execucao_ted_ne_vinculo.grupo_regra). Instrumento mesclado ("A + B", "NC_A / NC_B") é
  a junção que o crédito não permite separar.

  Restos a pagar (execucao_ted_ne), na linha do ano de emissão da NE: rap_inscrito é o
  que passou para restos a pagar no fim do ano, pago_rap o que foi pago depois e
  rap_a_pagar o que falta pagar no último exercício do relatório. pago_total = pago +
  pago_rap.
#}
with
    vinculo as (
        select
            v.ano,
            coalesce(v.instrumento, '(não identificado)') as instrumento,
            v.tipo_instrumento,
            v.grupo_regra,
            v.emp,
            v.liq,
            v.pag,
            b.insc_rap,
            b.pag_rap,
            b.saldo_rap
        from {{ ref("execucao_ted_ne_vinculo") }} as v
        inner join {{ ref("execucao_ted_ne") }} as b on b.ne_ccor = v.ne_ccor
    ),

    planos as (
        select distinct
            on (sq_instrumento)
            sq_instrumento,
            sigla_unidade_descentralizada,
            left(regexp_replace(tx_objeto_plano_acao, '\s+', ' ', 'g'), 200) as objeto
        from {{ ref("ted_plano_acao_consolidado") }}
        where sq_instrumento is not null
        order by sq_instrumento, id_plano_acao
    ),

    -- tedinho identificado na página do gov.br: nome pelo processo; instrumento
    -- mesclado ("A + B") recebe o nome, o parceiro e o objeto de cada parte (do plano
    -- de ação ou da página)
    pagina as (select * from {{ ref("ted_tedinho_gov_br") }}),

    partes as (
        select i.instrumento, p.parte, p.ordem
        from (select distinct instrumento from vinculo) as i
        cross join lateral unnest(string_to_array(i.instrumento, ' + '))
        with ordinality as p(parte, ordem)
    ),

    nomes as (
        select
            pt.instrumento,
            string_agg(
                coalesce(pg.nome_instrumento, pt.parte), ' + ' order by pt.ordem
            ) as nome_instrumento,
            string_agg(pg.processo, '; ' order by pt.ordem) as processo_gov_br,
            string_agg(
                coalesce(pl.sigla_unidade_descentralizada, pg.parceiro_sigla, '?'),
                ' + '
                order by pt.ordem
            ) as parceiro_partes,
            string_agg(
                coalesce(pl.objeto, left(pg.objeto, 200), '?'), ' | ' order by pt.ordem
            ) as objeto_partes,
            bool_or(
                pl.sigla_unidade_descentralizada is not null
                or pg.parceiro_sigla is not null
            ) as tem_parceiro,
            bool_or(pl.objeto is not null or pg.objeto is not null) as tem_objeto
        from partes as pt
        left join pagina as pg on pg.instrumento = pt.parte
        left join planos as pl on pl.sq_instrumento = pt.parte
        group by pt.instrumento
    )

select
    v.ano,
    v.instrumento,
    max(v.tipo_instrumento) as tipo_instrumento,
    round(sum(v.emp), 2) as empenhado,
    round(sum(v.liq), 2) as liquidado,
    round(sum(v.pag), 2) as pago,
    round(sum(v.insc_rap), 2) as rap_inscrito,
    round(sum(v.pag_rap), 2) as pago_rap,
    round(sum(v.pag + v.pag_rap), 2) as pago_total,
    round(sum(v.saldo_rap), 2) as rap_a_pagar,
    round(
        sum(v.emp) filter (where v.grupo_regra = '1 cascata dbt'), 2
    ) as empenhado_cascata_dbt,
    round(
        sum(v.emp) filter (where v.grupo_regra = '2 regras determinísticas'), 2
    ) as empenhado_regras_deterministicas,
    round(
        sum(v.emp) filter (where v.grupo_regra = '4 crédito da UG'), 2
    ) as empenhado_credito_ug,
    round(
        sum(v.emp) filter (where v.grupo_regra = '5 tedinho / subdescentralização'), 2
    ) as empenhado_tedinho_subdescentralizacao,
    round(
        sum(v.emp) filter (where v.grupo_regra = '6 não identificado'), 2
    ) as empenhado_nao_identificado,
    max(n.parceiro_partes) filter (where n.tem_parceiro) as parceiro,
    max(n.objeto_partes) filter (where n.tem_objeto) as objeto,
    max(n.nome_instrumento) as nome_instrumento,
    max(n.processo_gov_br) as processo_gov_br
from vinculo as v
left join nomes as n on n.instrumento = v.instrumento
group by v.ano, v.instrumento
