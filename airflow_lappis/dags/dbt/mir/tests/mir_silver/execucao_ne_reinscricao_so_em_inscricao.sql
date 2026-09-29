-- Falha se uma linha marcada como reinscricao de restos a pagar nao for linha
-- de inscricao, ou se a primeira inscricao de alguma NE vier marcada como
-- reinscricao (a NE precisa ter ao menos uma inscricao que conta).
select ne_ccor, 'reinscricao fora de linha de inscricao' as problema
from {{ ref("execucao_ne") }}
where reinscricao_rap and not inscricao_rap

union all

select ne_ccor, 'NE com inscricao so em reinscricoes' as problema
from {{ ref("execucao_ne") }}
where inscricao_rap and restos_a_pagar_inscritos <> 0
group by ne_ccor
having bool_and(reinscricao_rap)
