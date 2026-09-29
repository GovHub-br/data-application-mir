{{ config(severity="warn") }}

-- Aviso (nao bloqueia a DAG): NCs que citam TED no texto, sem numero de
-- transferencia no campo, no texto nem no processo, e por isso ficam fora do
-- mart de TEDs (ex.: "TED MIR E FIOCRUZ", "DIVERSOS TERMOS DE FOMENTO,
-- CONVENIOS E TEDS"). Linha de base em 2026-09-29: 0 (as 25 que existiam eram
-- NCs internas do MIR, que ficam fora de proposito).
select t.nc, t.nc_evento_descricao, t.valor_celula, t.descricao
from {{ ref("nc_tesouro_mir") }} as t
where
    coalesce(t.dc, 'ORIGEM') = 'ORIGEM'
    and t.nc_transferencia = '-8'
    -- NCs internas do MIR ficam fora de proposito (o credito chega ao executor
    -- pela NC seguinte)
    and not (
        left(t.nc, 6) in (select ug_codigo from {{ ref("ugs_mir") }})
        and t.favorecido_doc in (select ug_codigo from {{ ref("ugs_mir") }})
    )
    and upper(coalesce(t.descricao, '')) ~ '\mTEDS?\M|EXECUCAO DESCENTRALIZADA'
    and t.nc not in (select nc from {{ ref("ted_credito_nc") }})
