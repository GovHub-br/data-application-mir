-- Uma linha por ano x instrumento.
select ano, instrumento, count(*) as linhas
from {{ ref("ted_execucao_por_instrumento") }}
group by ano, instrumento
having count(*) > 1
