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
#}
with
    vinculo as (
        select
            ano,
            coalesce(instrumento, '(não identificado)') as instrumento,
            tipo_instrumento,
            grupo_regra,
            emp,
            liq,
            pag
        from {{ ref("execucao_ted_ne_vinculo") }}
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
    -- mesclado ("A + B") recebe o nome de cada parte
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
            string_agg(pg.parceiro_sigla, ' + ' order by pt.ordem) as parceiro_gov_br,
            string_agg(left(pg.objeto, 200), ' | ' order by pt.ordem) as objeto_gov_br
        from partes as pt
        left join pagina as pg on pg.instrumento = pt.parte
        group by pt.instrumento
    )

select
    v.ano,
    v.instrumento,
    max(v.tipo_instrumento) as tipo_instrumento,
    round(sum(v.emp), 2) as empenhado,
    round(sum(v.liq), 2) as liquidado,
    round(sum(v.pag), 2) as pago,
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
    coalesce(max(p.sigla_unidade_descentralizada), max(n.parceiro_gov_br)) as parceiro,
    coalesce(max(p.objeto), max(n.objeto_gov_br)) as objeto,
    max(n.nome_instrumento) as nome_instrumento,
    max(n.processo_gov_br) as processo_gov_br
from vinculo as v
left join planos as p on p.sq_instrumento = v.instrumento
left join nomes as n on n.instrumento = v.instrumento
group by v.ano, v.instrumento
