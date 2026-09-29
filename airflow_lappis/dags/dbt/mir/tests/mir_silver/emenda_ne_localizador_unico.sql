-- Falha se alguma NE de emenda tiver mais de um localizador do gasto no
-- tg_emendas: o emenda_ne guarda um so por NE.
select ne_ccor
from {{ ref("tg_emendas") }}
where ne_ccor in (select ne_ccor from {{ ref("emenda_ne") }})
group by ne_ccor
having count(distinct localizador_gasto) > 1
