{{ config(severity="warn") }}

{#
  Não se paga mais do que se empenhou. É aviso porque as NEs da UG 364150 do CNPq misturam
  empenho em dólar e RAP em real até a reextração no Tesouro Gerencial (ver
  test_ted_execucao_por_instrumento_pago_total_le_empenhado). Fora disso, o estouro indica
  pagamento contado duas vezes ou NE de outro instrumento somada ao TED.
#}
select id_plano_acao, ds_origem_execucao, vl_empenhado, vl_pago
from {{ ref("coleta_ted_execucao") }}
where vl_pago > vl_empenhado
