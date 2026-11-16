{{ config(severity="warn") }}

{#
  O fim da vigência só muda por termo aditivo ou por prorrogação de ofício (atraso no
  repasse, tabela prorroga_oficio). Um convênio sem nenhum dos dois com o fim diferente
  do original é um aditivo que a fonte não trouxe; o formulário diria "sem aditivos"
  com uma vigência que o gestor não reconhece.
#}
select c.nr_convenio, c.dt_fim_vigencia_original, c.dt_fim_vigencia
from {{ ref("coleta_convenio") }} as c
where
    c.qt_aditivos = 0
    and c.dt_fim_vigencia is distinct from c.dt_fim_vigencia_original
    and not exists (
        select 1 from {{ ref("prorroga_oficio") }} as o where o.nr_convenio = c.nr_convenio
    )
