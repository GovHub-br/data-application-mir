{{ config(materialized="table") }}

-- Planejamento Estrategico Institucional (Bloco 3.3). Passa pelo contrato para
-- o Coleta ler tudo do schema coleta_mir.
select nivel, codigo, codigo_pai, titulo
from {{ ref("pei_mir") }}
