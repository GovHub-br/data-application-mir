{{ config(materialized="table") }}

{#
  Execução dos TEDs do MIR por NE (analises/ted_execucao/pipeline.py,
  saida/execucao_por_ne.csv e ne_nao_identificadas.csv): cada NE da consulta oficial
  "Execução TED por UG" com o instrumento e a regra que o identificou.
  Grão: uma linha por NE.
#}
with
    nomes as (
        select distinct on (ug_executora_codigo)
            ug_executora_codigo, ug_executora_nome, orgao_uge_nome
        from {{ ref("execucao_ted_ug") }}
        order by ug_executora_codigo, ano_lancamento desc
    )

select
    v.ano,
    v.ne_ccor,
    v.ug,
    n.ug_executora_nome as ug_nome,
    v.orgao_ug,
    n.orgao_uge_nome as orgao_nome,
    b.acao,
    b.po,
    v.ptres,
    v.fonte,
    b.grupo,
    b.favorecido,
    b.processo,
    b.ne_ccor_descricao,
    v.instrumento,
    v.tipo_instrumento,
    v.regra,
    v.grupo_regra,
    v.emp as empenhado,
    v.liq as liquidado,
    v.pag as pago
from {{ ref("execucao_ted_ne_vinculo") }} as v
inner join {{ ref("execucao_ted_ne") }} as b on b.ne_ccor = v.ne_ccor
left join nomes as n on n.ug_executora_codigo = v.ug
