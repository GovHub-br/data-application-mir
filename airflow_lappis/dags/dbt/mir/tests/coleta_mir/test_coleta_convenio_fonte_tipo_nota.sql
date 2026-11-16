{#
  coleta_convenio_fonte soma valor_empenho direto porque, nos tipos de nota de hoje, ele
  já é o valor líquido da NE. Um tipo fora da lista nos convênios do universo pode mudar
  isso (ex.: a anulação de pré-empenho dos tipos antigos vem positiva) e o empenhado
  sairia errado. O teste é de erro para ficar vermelho no Cosmos; a tabela já terá sido
  trocada, então alguém confere o tipo novo e o acrescenta aqui ou trata no modelo.
#}
select e.nr_convenio, e.nr_empenho, e.desc_tipo_nota, e.valor_empenho
from {{ ref("empenho") }} as e
inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = e.nr_convenio
-- Pela fonte, para o teste rodar junto com ela.
where
    e.nr_convenio in (select nr_convenio from {{ ref("coleta_convenio_fonte") }})
    and e.desc_tipo_nota not in ('Ordinário', 'Global', 'Estimativo', 'Empenho Original')
