{{ config(severity="warn") }}

{#
  O fim da vigência só muda por termo aditivo ou por prorrogação de ofício. Um convênio
  sem aditivo com o fim diferente do original foi prorrogado de ofício (atraso no
  repasse) ou a fonte não trouxe o aditivo; o formulário diria "sem aditivos" com uma
  vigência que o gestor não reconhece.
#}
select nr_convenio, dt_fim_vigencia_original, dt_fim_vigencia
from {{ ref("coleta_convenio") }}
where qt_aditivos = 0 and dt_fim_vigencia is distinct from dt_fim_vigencia_original
