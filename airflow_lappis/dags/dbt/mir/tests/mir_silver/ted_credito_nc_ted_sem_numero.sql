{{ config(severity="warn", warn_if=">25") }}

-- Aviso (nao bloqueia a DAG): NCs que citam TED no texto, sem numero de
-- transferencia no campo, no texto nem no processo, e por isso ficam fora do
-- mart de TEDs (ex.: "TED MIR E FIOCRUZ", "DIVERSOS TERMOS DE FOMENTO,
-- CONVENIOS E TEDS"). Linha de base em 2026-09-29: 25 linhas (R$ 14,5 mi); o
-- aviso so dispara se o numero crescer.
select t.nc, t.nc_evento_descricao, t.valor_celula, t.descricao
from {{ ref("nc_tesouro_mir") }} as t
where
    coalesce(t.dc, 'ORIGEM') = 'ORIGEM'
    and t.nc_transferencia = '-8'
    and upper(coalesce(t.descricao, '')) ~ '\mTEDS?\M|EXECUCAO DESCENTRALIZADA'
    and t.nc not in (select nc from {{ ref("ted_credito_nc") }})
