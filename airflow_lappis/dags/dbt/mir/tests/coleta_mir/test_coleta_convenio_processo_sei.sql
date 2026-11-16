{{ config(severity="warn") }}

{#
  O número SEI sai com máscara quando a fonte traz os 17 dígitos do SEI; senão, como
  veio. Os convênios antigos trazem o número de processo anterior ao SEI e ficam assim.
  Este teste avisa quando um convênio assinado a partir de 2023 não traz o SEI: o gestor
  vai ver no formulário um número que não acha no SEI.
#}
select nr_convenio, dt_assinatura, nr_processo
from {{ ref("coleta_convenio") }}
where
    dt_assinatura >= '2023-01-01'
    and (nr_processo is null or nr_processo !~ '^[0-9]{5}\.[0-9]{6}/[0-9]{4}-[0-9]{2}$')
