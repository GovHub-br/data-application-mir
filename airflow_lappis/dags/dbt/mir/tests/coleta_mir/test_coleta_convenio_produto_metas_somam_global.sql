{{ config(severity="warn") }}

{#
  As metas de um convênio repartem o valor global dele. Quando a soma não fecha, há meta
  a mais (o plano foi refeito e a meta antiga continuou na carga) ou a menos, e o gestor
  vê no item 5.2 produtos que não são os do plano vigente.
#}
select c.nr_convenio, c.vl_global, sum(p.vl_item) as vl_metas
from {{ ref("coleta_convenio") }} as c
inner join {{ ref("coleta_convenio_produto") }} as p on p.nr_convenio = c.nr_convenio
where p.tp_nivel = 'meta'
group by c.nr_convenio, c.vl_global
having c.vl_global is distinct from sum(p.vl_item)
