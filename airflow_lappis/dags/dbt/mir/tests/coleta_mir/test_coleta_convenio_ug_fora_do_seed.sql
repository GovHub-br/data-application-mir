{{ config(severity="warn") }}

{#
  A unidade concedente sai da UG responsável dos empenhos, procurada no seed
  coleta_unidade_mir. Uma UG do MIR (seed ugs_mir) que não está lá deixaria o convênio
  com a unidade do ministério, sem erro. A correção é acrescentar a linha no seed. UGs
  de outros órgãos (as de convênios antigos, da época da SEPPIR) ficam de fora.
#}
select e.ug_responsavel, count(distinct e.nr_convenio) as convenios
from {{ ref("empenho") }} as e
inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = e.nr_convenio
inner join {{ ref("ugs_mir") }} as m on m.ug_codigo = e.ug_responsavel::text
left join {{ ref("coleta_unidade_mir") }} as u on u.cd_ug = e.ug_responsavel::text
where u.cd_ug is null
group by e.ug_responsavel
