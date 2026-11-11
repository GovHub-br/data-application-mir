{{ config(severity="warn") }}

{#
  O fallback do gov.br pode trazer para um TED o processo de um tedinho: a página de
  transferências do MIR publica os dois lado a lado, e ela já erra uma vez — o TED 978641
  (UFRGS) recebe dela o processo do tedinho da UNIVASF, que tedinhos_identificados_mir
  registra. Nesse caso o termo tem o processo e vence, mas nos 25 TEDs sem processo no
  termo não há com o que comparar e o valor da página entra como está.

  Este teste avisa quando o processo que entrou pelo gov.br é um que o seed de tedinhos
  conhece: aí o TED está com o processo do instrumento errado, e a correção é tirar esse
  num_transf do fallback. Hoje nenhum dos 25 colide.
#}
select
    t.nr_transferencia,
    t.aa_instrumento,
    t.sg_parceiro,
    t.nr_processo_sei,
    ti.orgao_parceiro as tedinho_parceiro,
    ti.observacao as tedinho_observacao
from {{ ref("coleta_ted") }} as t
join
    {{ ref("tedinhos_identificados_mir") }} as ti
    on regexp_replace(ti.processo, '\D', '', 'g')
    = regexp_replace(t.nr_processo_sei, '\D', '', 'g')
where t.ds_origem_sei = 'gov_br'
