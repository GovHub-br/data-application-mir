-- Duas linhas para o mesmo (ug_emitente, ano_emissao) fazem o left join de
-- ppa_tesouro duplicar cada NE do par.
select ug_emitente, ano_emissao, count(*)
from {{ ref("cambio_fechamento_exercicio") }}
group by ug_emitente, ano_emissao
having count(*) > 1
