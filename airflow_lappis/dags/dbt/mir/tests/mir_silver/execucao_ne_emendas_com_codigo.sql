-- Falha se alguma NE de emenda (tg_emendas) presente no ppa_tesouro ficar sem
-- codigo_emenda / origem Emenda em execucao_ne.
select distinct t.ne_ccor
from {{ ref("tg_emendas") }} as t
inner join {{ ref("execucao_ne") }} as e on e.ne_ccor = t.ne_ccor
where e.codigo_emenda is null or e.origem_recurso <> 'Emenda'
