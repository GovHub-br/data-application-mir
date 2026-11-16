{{ config(severity="warn") }}

{#
  tp_situacao_execucao traduz a situação do siconv para as opções do formulário. Fica
  nula quando a situação não tem opção: Inadimplente, prestação de contas já encerrada
  num instrumento assinado desde 2023, ou uma situação nova na fonte. A situação desses
  instrumentos precisa de alguém no Coleta; uma situação nova pede uma linha no case
  de coleta_convenio.
#}
select nr_convenio, tp_instrumento, ds_situacao
from {{ ref("coleta_convenio") }}
where tp_situacao_execucao is null
