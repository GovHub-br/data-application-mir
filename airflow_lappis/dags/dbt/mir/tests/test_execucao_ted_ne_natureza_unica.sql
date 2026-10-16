-- Uma natureza de despesa e uma descrição de fonte por NE: execucao_ted_ne guarda o
-- min() de cada uma, então uma NE com duas naturezas sumiria da distribuição por
-- natureza sem aviso.
select
    p.ne_ccor,
    count(distinct p.natureza_despesa) as naturezas,
    count(distinct p.fonte_recursos_detalhada_descricao) as fontes
from {{ ref("ppa_tesouro") }} as p
inner join {{ ref("execucao_ted_ne") }} as n on n.ne_ccor = p.ne_ccor
group by p.ne_ccor
having
    count(distinct p.natureza_despesa) > 1
    or count(distinct p.fonte_recursos_detalhada_descricao) > 1
