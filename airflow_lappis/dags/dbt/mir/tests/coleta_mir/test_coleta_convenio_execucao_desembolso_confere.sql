{{ config(severity="warn") }}

{#
  vl_desembolsado soma as linhas de desembolso. O próprio convênio traz o total
  (vl_desembolsado_conv, nulo quando não houve); se os dois divergirem, a tabela de
  desembolsos veio incompleta ou com linha repetida, e o formulário mostra um valor que
  o Transferegov não mostra.
#}
select e.nr_convenio, e.vl_desembolsado, c.vl_desembolsado_conv
from {{ ref("coleta_convenio_execucao") }} as e
inner join {{ ref("convenio") }} as c on c.nr_convenio = e.nr_convenio
where e.vl_desembolsado <> coalesce(c.vl_desembolsado_conv, 0)
