{{ config(severity="warn") }}

{#
  A origem sai do resultado primário da NE. Desde 2023, uma linha sem origem (NE sem
  resultado primário), com "Outra" (resultado primário fora de 2, 6, 7 e 8) ou com tipo
  de emenda mas sem número de emenda (a NE de RP 6, 7 ou 8 não está em
  numero_transferencia nem descreve a emenda) precisa de alguém no Coleta.
#}
select nr_convenio, aa_emissao, cd_ptres, tp_origem, cd_emenda, vl_empenhado
from {{ ref("coleta_convenio_fonte") }}
where
    aa_emissao >= 2023
    and (
        tp_origem is null
        or tp_origem = 'Outra'
        or (tp_origem like 'Emenda%' and cd_emenda = 'sem_emenda')
    )
