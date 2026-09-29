-- Cobertura do vinculo emenda -> instrumento. Linha de base em 2026-09-29: 25
-- NEs de emenda sem instrumento (contratos diretos, SIPAD, convenios antigos).
-- Falha se o numero subir: indica regressao na extracao do vinculo. Subir o
-- limite exige justificativa no PR.
select count(distinct ne_ccor) as nes_emenda_sem_instrumento
from {{ ref("execucao_ne") }}
where origem_recurso = 'Emenda' and sistema_instrumento = 'Não identificado'
having count(distinct ne_ccor) > 25
