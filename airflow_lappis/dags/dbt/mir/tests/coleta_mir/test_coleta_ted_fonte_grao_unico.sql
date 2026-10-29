{#
  coleta_ted_fonte tem uma linha por TED, ano, programa, ação, PTRES, fonte e natureza.
  A UO entra no group by, mas sai do PTRES; se o mesmo PTRES desse duas UOs, a linha se
  duplicaria e o crédito do TED seria contado duas vezes.
#}
select
    id_plano_acao,
    aa_emissao,
    cd_programa,
    cd_acao,
    cd_ptres,
    cd_fonte,
    cd_natureza_despesa,
    count(*) as qt
from {{ ref("coleta_ted_fonte") }}
group by 1, 2, 3, 4, 5, 6, 7
having count(*) > 1
