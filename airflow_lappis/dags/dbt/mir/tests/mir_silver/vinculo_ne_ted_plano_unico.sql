-- Falha se alguma NE apontar para mais de um plano de acao na cascata de TED.
-- vinculo_ne_ted consolida por NE com max(); este teste garante que o max()
-- nao esconde conflito entre linhas da mesma NE.
select t.ne_ccor, count(distinct p.id_plano_acao) as qtd_planos
from {{ ref("ted_ne_transferencia") }} as t
inner join {{ ref("ted_plano_instrumento") }} as p on p.num_transf = t.num_transf
group by t.ne_ccor
having count(distinct p.id_plano_acao) > 1
