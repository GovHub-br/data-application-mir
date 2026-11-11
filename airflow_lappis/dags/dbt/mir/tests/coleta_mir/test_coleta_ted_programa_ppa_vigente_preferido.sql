{#
  cd_programa_ppa escolhe um programa quando o TED tem crédito em mais de um (24 dos 105
  com crédito em 2026-11-11), e a primeira chave da escolha é estar na revisão vigente do
  PPA. Um TED que saiu com programa fora do PPA vigente tendo outro que está nele quer
  dizer que a ordem da escolha quebrou — e o Coleta perde o item 3.1 de um TED que tinha
  resposta na lista.

  Não é aviso: a regra garante isto por construção, então uma linha aqui é defeito da
  regra, não da realidade dos dados. Os TEDs cujo único programa é de PPA anterior ficam
  com in_programa_ppa_vigente = false e não aparecem aqui, que é o esperado.
#}
select
    c.id_plano_acao,
    c.nr_transferencia,
    c.cd_programa_ppa,
    array_agg(distinct n.programa_governo) as programas_do_ted
from {{ ref("coleta_ted") }} as c
join {{ ref("nc_unificado") }} as n on n.nc_transferencia = c.nr_transferencia
where
    c.in_programa_ppa_vigente is false
    and n.programa_governo in (
        select codigo
        from {{ ref("coleta_lista_ppa") }}
        where nivel = 'programa' and in_vigente
    )
group by c.id_plano_acao, c.nr_transferencia, c.cd_programa_ppa
