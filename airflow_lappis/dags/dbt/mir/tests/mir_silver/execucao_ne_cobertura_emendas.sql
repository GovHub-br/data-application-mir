{{ config(severity="warn") }}

-- Cobertura do vinculo emenda -> instrumento. Linha de base em 2026-09-29: 5 de
-- 221 NEs de emenda (2,3%) sem instrumento (execucao direta ou numero do
-- instrumento ausente dos textos da NE). Aviso (nao bloqueia a DAG) se a
-- fracao passar de 10%: indica regressao na extracao do vinculo ou um novo
-- formato de numero de instrumento.
select
    count(distinct ne_ccor) filter (
        where sistema_instrumento = 'Não identificado'
    ) as nes_emenda_sem_instrumento,
    count(distinct ne_ccor) as nes_emenda
from {{ ref("execucao_ne") }}
where origem_recurso = 'Emenda'
having
    count(distinct ne_ccor) filter (where sistema_instrumento = 'Não identificado')
    > 0.10 * count(distinct ne_ccor)
