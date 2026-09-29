{{ config(severity="warn") }}

-- Aviso (nao bloqueia a DAG): instrumentos de Emenda que tambem receberam NE de
-- recurso proprio (complemento ate o repasse minimo legal de R$ 200 mil). O caso
-- e legitimo, mas um numero crescente merece revisao. Linha de base em
-- 2026-09-29: 2 (965040, 965084).
select nr_convenio, origem_recurso
from {{ ref("convenio_mir") }}
where complemento_proprio
