{{ config(severity="warn") }}

{#
  A contrapartida aportada não deveria passar da pactuada. Quando passa, o convenente
  depositou a mais ou registrou como contrapartida outro ingresso (ex.: devolução de
  saldo); o gestor confere no Coleta.
#}
select e.nr_convenio, e.vl_contrapartida_aportada, c.vl_contrapartida
from {{ ref("coleta_convenio_execucao") }} as e
inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = e.nr_convenio
where e.vl_contrapartida_aportada > c.vl_contrapartida
