{{ config(severity="warn") }}

{#
  Todo convênio assinado tem plano de trabalho com ao menos uma meta. Sem meta em
  coleta_convenio_produto, o gestor não tem produto para escolher no item 5.2: a meta
  não veio na carga ou mudou de proposta.
#}
select c.nr_convenio, c.id_proposta
from {{ ref("coleta_convenio") }} as c
left join
    {{ ref("coleta_convenio_produto") }} as p
    on p.nr_convenio = c.nr_convenio
    and p.tp_nivel = 'meta'
where p.id_origem is null
