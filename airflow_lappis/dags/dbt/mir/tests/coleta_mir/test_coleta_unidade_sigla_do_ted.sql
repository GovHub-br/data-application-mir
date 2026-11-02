{{ config(severity="warn") }}

{#
  O Coleta liga coleta_ted.sg_unidade_acompanhamento a coleta_unidade.sg_unidade para ter
  o código Siorg e o CNPJ da unidade (Bloco 2). O seed é uma lista manual e o portal TED
  pode criar outra sigla: os TEDs dela ficariam sem os dois campos, sem erro. Este teste
  avisa; a correção é acrescentar a linha em coleta_unidade_mir.
#}
select t.sg_unidade_acompanhamento, count(*) as teds
from {{ ref("coleta_ted") }} as t
left join {{ ref("coleta_unidade") }} as u on u.sg_unidade = t.sg_unidade_acompanhamento
where u.sg_unidade is null
group by t.sg_unidade_acompanhamento
