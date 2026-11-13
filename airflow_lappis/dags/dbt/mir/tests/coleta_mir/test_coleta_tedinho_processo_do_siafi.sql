{{ config(severity="warn") }}

{#
  coleta_tedinho tem como espinha o seed tedinhos_identificados_mir, que é levantamento
  manual. Hoje o seed é superconjunto do que o SIAFI resolve (23 processos contra 19), e
  nenhum processo aparece só do lado do SIAFI.

  Se a raspagem do gov.br passar a achar um tedinho que o seed não tem, ele ficaria fora
  do contrato em silêncio e o Coleta não teria o que preencher. Este teste avisa; a
  correção é acrescentar a linha em tedinhos_identificados_mir.
#}
select g.processo, g.parceiro_sigla, g.valor_pagina, g.pagina, g.instrumento
from {{ ref("ted_tedinho_gov_br") }} as g
where
    g.processo is not null
    and not exists (
        select 1
        from {{ ref("coleta_tedinho") }} as c
        where
            regexp_replace(c.nr_processo_sei, '\D', '', 'g')
            = regexp_replace(g.processo, '\D', '', 'g')
    )
