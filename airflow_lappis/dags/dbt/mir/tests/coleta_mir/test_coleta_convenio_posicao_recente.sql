{{ config(severity="warn") }}

{#
  dt_posicao é a data do último evento do siconv. Com mais de 45 dias, a carga do
  siconv parou (foi o que aconteceu quando o Transferegov tirou o siconv.zip do ar em
  07/2026) e o formulário mostra situação e valores velhos. Nula, o histórico veio
  vazio.
#}
select distinct dt_posicao
from {{ ref("coleta_convenio") }}
where dt_posicao is null or dt_posicao < current_date - 45
