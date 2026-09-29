-- execucao_ne atribui a emenda por NE assumindo no maximo uma emenda por NE no
-- tg_emendas; mais de uma multiplicaria as linhas da execucao. Este teste
-- aponta a causa diretamente, antes da reconciliacao acusar diferenca de somas.
select ne_ccor, count(distinct autor_emendas_orcamento) as qtd_emendas
from {{ ref("tg_emendas") }}
group by ne_ccor
having count(distinct autor_emendas_orcamento) > 1
