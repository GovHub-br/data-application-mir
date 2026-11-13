{{ config(severity="warn") }}

{#
  A NE de reforço não está em numero_transferencia e só descreve a emenda com 8 dígitos,
  sem o ano. Ela é resolvida para os 12 dígitos pelas outras NEs do convênio; quando
  nenhuma dá o código, fica com 8 e a mesma emenda pode aparecer com dois números no
  formulário.
#}
select nr_convenio, aa_emissao, cd_emenda, no_autor_emenda, vl_empenhado
from {{ ref("coleta_convenio_fonte") }}
where cd_emenda ~ '^[0-9]{8}$'
