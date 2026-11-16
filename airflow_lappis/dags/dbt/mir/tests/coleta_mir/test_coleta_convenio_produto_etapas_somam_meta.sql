{{ config(severity="warn") }}

{#
  vl_item da meta é o total dela, e as etapas repartem esse total. Quando a soma das
  etapas não dá o valor da meta, o plano de trabalho foi alterado só em um dos níveis e
  o gestor vê dois valores para o mesmo produto.
#}
select m.id_origem, m.nr_convenio, m.vl_item as vl_meta, sum(e.vl_item) as vl_etapas
from {{ ref("coleta_convenio_produto") }} as m
inner join {{ ref("coleta_convenio_produto") }} as e on e.id_origem_pai = m.id_origem
where m.tp_nivel = 'meta'
group by m.id_origem, m.nr_convenio, m.vl_item
having m.vl_item is distinct from sum(e.vl_item)
