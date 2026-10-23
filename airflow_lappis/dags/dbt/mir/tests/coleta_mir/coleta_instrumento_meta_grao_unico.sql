-- Falha se houver mais de uma linha por instrumento x id_origem. O nr_etapa
-- pode se repetir dentro da mesma meta na fonte (etapas distintas com o mesmo
-- numero), por isso o grao e o id da meta/etapa na origem, nao a numeracao.
select chave_instrumento, id_origem, count(*) as linhas
from {{ ref("coleta_instrumento_meta") }}
group by chave_instrumento, id_origem
having count(*) > 1
