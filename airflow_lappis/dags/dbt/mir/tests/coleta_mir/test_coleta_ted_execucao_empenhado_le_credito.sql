{{ config(severity="warn") }}

{#
  Empenho acima do crédito que ficou com o TED, inclusive empenho sem NC carregada. É
  aviso porque a NE pode ter sido atribuída ao TED errado, mas a falta também pode estar
  do lado do crédito (NC de outro exercício que não foi carregada).
#}
select id_plano_acao, ds_origem_execucao, vl_empenhado, vl_credito_liquido
from {{ ref("coleta_ted_execucao") }}
where vl_empenhado > coalesce(vl_credito_liquido, 0)
