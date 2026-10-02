-- Falha se um instrumento aparecer mais de uma vez em emenda_instrumento.
select sistema_instrumento, nr_instrumento, count(*) as qtd
from {{ ref("emenda_instrumento") }}
group by sistema_instrumento, nr_instrumento
having count(*) > 1
