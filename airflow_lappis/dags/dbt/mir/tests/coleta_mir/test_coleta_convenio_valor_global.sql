{{ config(severity="warn") }}

{#
  O formulário mostra repasse, contrapartida e valor global lado a lado; o global deve
  ser a soma dos dois mais o rendimento de aplicação que o convenente foi autorizado a
  usar (comum nos termos de fomento). A fonte grava os valores separados e um aditivo
  pode atualizar um sem o outro.
#}
select nr_convenio, vl_repasse, vl_contrapartida, vl_rendimento_aplicacao, vl_global
from {{ ref("coleta_convenio") }}
where vl_global is distinct from vl_repasse + vl_contrapartida + vl_rendimento_aplicacao
