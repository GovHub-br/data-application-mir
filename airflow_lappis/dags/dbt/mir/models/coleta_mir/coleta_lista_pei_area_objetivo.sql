{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 3.3 do formulário de TEDs: os pares de área e objetivo
  estratégico do PEI, que são N:N e não cabem em chave_pai de coleta_lista_pei.

  Só entra o par escrito no PEI: o selo "Atribuições da ..." da página de cada objetivo. O
  PEI cita as secretarias finalísticas, não as diretorias, então diretoria de SEPAR,
  SENAPIR ou SQPT não tem par próprio: quem lê sobe pela chave_pai da área.
#}
select distinct
    ('area:' || codigo_area)::text as chave_area,
    ('objetivo_estrategico:' || codigo_objetivo_estrategico)::text as chave_objetivo
from {{ ref("coleta_pei_objetivo_especifico") }}
