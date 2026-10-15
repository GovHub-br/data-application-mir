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
        select distinct on (sq_instrumento)
            sq_instrumento,
            sigla_unidade_descentralizada,
            left(regexp_replace(tx_objeto_plano_acao, '\s+', ' ', 'g'), 200) as objeto
        from {{ ref("ted_plano_acao_consolidado") }}
        where sq_instrumento is not null
        order by sq_instrumento, id_plano_acao
    )

select
    v.ano,
    v.instrumento,
    max(v.tipo_instrumento) as tipo_instrumento,
    round(sum(v.emp), 2) as empenhado,
    round(sum(v.liq), 2) as liquidado,
    round(sum(v.pag), 2) as pago,
    round(sum(v.emp) filter (where v.grupo_regra = '1 cascata dbt'), 2) as empenhado_cascata_dbt,
    round(sum(v.emp) filter (where v.grupo_regra = '2 regras determinísticas'), 2)
    as empenhado_regras_deterministicas,
    round(sum(v.emp) filter (where v.grupo_regra = '4 crédito da UG'), 2) as empenhado_credito_ug,
    round(sum(v.emp) filter (where v.grupo_regra = '5 tedinho / subdescentralização'), 2)
    as empenhado_tedinho_subdescentralizacao,
    round(sum(v.emp) filter (where v.grupo_regra = '6 não identificado'), 2)
    as empenhado_nao_identificado,
    max(p.sigla_unidade_descentralizada) as parceiro,
    max(p.objeto) as objeto
from vinculo as v
left join planos as p on p.sq_instrumento = v.instrumento
group by v.ano, v.instrumento
