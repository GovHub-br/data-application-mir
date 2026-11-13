{#
  coleta_convenio_fonte soma valor_empenho direto porque, nos tipos de nota de hoje, ele
  já é o valor líquido da NE. Um tipo novo nos convênios do universo pode mudar isso
  (ex.: anulação em linha própria com valor positivo) e o empenhado sairia errado sem
  aviso. O build para até alguém conferir o tipo novo e acrescentá-lo aqui.
#}
select e.nr_convenio, e.nr_empenho, e.desc_tipo_nota, e.valor_empenho
from {{ ref("empenho") }} as e
inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = e.nr_convenio
-- Pela fonte, para o teste rodar junto com ela.
where
    e.nr_convenio in (select nr_convenio from {{ ref("coleta_convenio_fonte") }})
    and e.desc_tipo_nota not in ('Ordinário', 'Empenho Original')
