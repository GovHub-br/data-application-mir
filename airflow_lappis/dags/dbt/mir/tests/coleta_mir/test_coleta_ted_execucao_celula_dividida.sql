{{ config(severity="warn") }}

{#
  Para os TEDs fora da consulta oficial, coleta_ted_execucao liga as NEs pela célula (UG
  favorecida da NC, PTRES). Hoje cada célula é de um TED só. Se dois TEDs dividirem uma, as
  NEs não são atribuídas e os dois saem como sem_dado, então a regra precisa ser revista.
#}
select n.favorecido_doc as ug, n.ptres, array_agg(distinct c.nr_transferencia) as teds
from {{ ref("coleta_ted_execucao") }} as e
join {{ ref("coleta_ted") }} as c on c.id_plano_acao = e.id_plano_acao
join {{ ref("nc_unificado") }} as n on n.nc_transferencia = c.nr_transferencia
where n.relatorio = 'enviadas' and e.ds_origem_execucao <> 'consulta_oficial'
group by n.favorecido_doc, n.ptres
having count(distinct c.id_plano_acao) > 1
