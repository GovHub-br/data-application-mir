{{ config(severity="warn") }}

{#
  Quando os empenhos de um convênio têm como UG responsável mais de uma secretaria,
  coleta_convenio não escolhe e põe o ministério como unidade concedente. Este teste
  lista esses convênios para alguém confirmar a unidade no Coleta.
#}
select e.nr_convenio, string_agg(distinct u.sg_unidade, ', ') as secretarias
from {{ ref("empenho") }} as e
inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = e.nr_convenio
inner join {{ ref("coleta_unidade_mir") }} as u on u.cd_ug = e.ug_responsavel::text
where u.cd_ug <> '810008'
group by e.nr_convenio
having count(distinct u.sg_unidade) > 1
