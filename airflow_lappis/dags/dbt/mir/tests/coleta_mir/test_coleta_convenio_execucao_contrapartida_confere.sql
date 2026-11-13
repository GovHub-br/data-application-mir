{{ config(severity="warn") }}

{#
  vl_contrapartida_aportada soma as linhas de ingresso_contrapartida, que não tem chave
  na fonte. O convênio traz o total (vl_ingresso_contrapartida, nulo quando não houve);
  se divergirem, a tabela veio incompleta ou com linha repetida.
#}
select e.nr_convenio, e.vl_contrapartida_aportada, c.vl_ingresso_contrapartida
from {{ ref("coleta_convenio_execucao") }} as e
inner join {{ ref("convenio") }} as c on c.nr_convenio = e.nr_convenio
where e.vl_contrapartida_aportada <> coalesce(c.vl_ingresso_contrapartida, 0)
