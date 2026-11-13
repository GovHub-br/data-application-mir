{{ config(severity="warn") }}

{#
  O formulário mostra repasse, contrapartida e valor global lado a lado; o global deve
  ser a soma dos outros dois. A fonte grava os três separados e um aditivo pode
  atualizar um sem o outro.
#}
select nr_convenio, vl_repasse, vl_contrapartida, vl_global
from {{ ref("coleta_convenio") }}
where vl_global is distinct from vl_repasse + vl_contrapartida
