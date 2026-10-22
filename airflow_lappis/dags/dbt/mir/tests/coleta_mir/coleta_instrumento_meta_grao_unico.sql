-- Falha se houver mais de uma linha por instrumento x meta x etapa. A linha da
-- propria meta tem nr_etapa nulo; coalesce(-1) evita que nulos escapem do
-- group by.
select chave_instrumento, nr_meta, coalesce(nr_etapa, -1) as nr_etapa, count(*) as linhas
from {{ ref("coleta_instrumento_meta") }}
group by chave_instrumento, nr_meta, coalesce(nr_etapa, -1)
having count(*) > 1
