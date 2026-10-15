-- Falha se as rodadas fixas da execução por instrumento podem não ter bastado: a
-- propagação B/C/E (execucao_ted_ne_regras) e o casamento de saldos (ted_casar_saldos, em
-- execucao_ted_ne_vinculo) param depois de var('ted_execucao_rodadas') rodadas; se a
-- última ainda ligou alguma NE, pode haver NE que uma rodada a mais ligaria. Também falha
-- se uma célula tem mais devoluções sem par do que ted_saldo_celula abate (5).
-- Correção: aumentar a var ted_execucao_rodadas (ou max_devolucoes na macro).
{% set ultima = var("ted_execucao_rodadas", 8) - 1 %}

select 'propagação' as etapa, ne_ccor, regra
from {{ ref("execucao_ted_ne_regras") }}
where rodada_propagacao = {{ ultima }}

union all

select 'casamento de saldos', ne_ccor, regra
from {{ ref("execucao_ted_ne_vinculo") }}
where modo_casamento in ('exato', 'grupo', 'subconjunto') and rodada = {{ ultima }}

union all

select 'devoluções sem par', celula_credito, count(distinct nc)::text
from {{ ref("ted_credito_instrumento") }}
where instrumento = '(devolução sem TED)'
group by celula_credito
having count(distinct nc) > 5
