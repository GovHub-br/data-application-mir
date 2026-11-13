{{ config(severity="warn") }}

{#
  O desembolso sai do empenho, então não deveria passar dele. Quando passa, o siconv não
  tem todos os empenhos do convênio e o item 3.5 do formulário mostra só parte da origem
  dos recursos. Nos anteriores a 2023 isso é sabido (7 em 11/2026, descrito em
  coleta_convenio_fonte) e eles ficam de fora, para o aviso só acender em caso novo.
#}
with
    desembolso as (
        select nr_convenio, sum(vl_desembolsado) as vl_desembolsado
        from {{ ref("desembolso") }}
        group by nr_convenio
    ),

    empenho as (
        select nr_convenio, sum(vl_empenhado) as vl_empenhado
        from {{ ref("coleta_convenio_fonte") }}
        group by nr_convenio
    )

select c.nr_convenio, c.dt_assinatura, d.vl_desembolsado, e.vl_empenhado
from {{ ref("coleta_convenio") }} as c
inner join desembolso as d on d.nr_convenio = c.nr_convenio
left join empenho as e on e.nr_convenio = c.nr_convenio
where
    d.vl_desembolsado > coalesce(e.vl_empenhado, 0)
    and c.dt_assinatura >= '2023-01-01'
