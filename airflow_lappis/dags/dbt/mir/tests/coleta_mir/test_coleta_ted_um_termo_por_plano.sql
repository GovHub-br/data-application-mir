{{ config(severity="warn") }}

{#
  O coleta_ted tira o processo SEI e a data de celebração do primeiro termo assinado do
  plano, sem olhar a situação do termo. Hoje cada plano tem um termo só. Se um plano
  passar a ter mais de um (ex.: um termo cancelado e outro assinado depois), a escolha
  precisa ser revista.
#}
select id_plano_acao, count(*) as termos
from {{ ref("termos_execucao_ted") }}
group by id_plano_acao
having count(*) > 1
