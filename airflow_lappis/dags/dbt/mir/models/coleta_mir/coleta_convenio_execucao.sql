{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, Bloco 1 do formulário de convênios ("Valor liberado /
  desembolsado") e sugestão do item 4.3 (contrapartida aportada): uma linha por
  convênio de coleta_convenio. Fica fora de coleta_convenio, como coleta_ted_execucao
  fica fora de coleta_ted, para os valores de execução crescerem sem mexer no contrato de
  identificação.

  No siconv a ausência de desembolso ou de ingresso de contrapartida é dado: o convênio
  ainda não recebeu ou não aportou. Os dois valores ficam 0, nunca nulos. Com a carga do
  siconv parada, 0 pode estar velho: ler junto com coleta_convenio.dt_posicao.
#}
with
    desembolso as (
        select nr_convenio, sum(vl_desembolsado) as vl_desembolsado
        from {{ ref("desembolso") }}
        group by nr_convenio
    ),

    contrapartida as (
        select nr_convenio, sum(vl_ingresso_contrapartida) as vl_contrapartida_aportada
        from {{ ref("ingresso_contrapartida") }}
        group by nr_convenio
    )

select
    c.nr_convenio::text as nr_convenio,
    coalesce(d.vl_desembolsado, 0)::numeric(15, 2) as vl_desembolsado,
    coalesce(k.vl_contrapartida_aportada, 0)::numeric(15, 2)
    as vl_contrapartida_aportada
from {{ ref("coleta_convenio") }} as c
left join desembolso as d on d.nr_convenio = c.nr_convenio
left join contrapartida as k on k.nr_convenio = c.nr_convenio
