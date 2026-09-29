-- Falha se uma UG do MIR aparecer como unidade executora de TED: o executor e
-- sempre o lado da NC ou da PF que nao e o MIR.
select ug_executora_codigo, ug_executora_nome
from {{ ref("ted_unidade_executora") }}
where ug_executora_codigo in (select ug_codigo from {{ ref("ugs_mir") }})
