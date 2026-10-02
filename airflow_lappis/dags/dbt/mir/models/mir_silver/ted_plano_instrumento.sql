{{ config(materialized="table") }}

-- Numero da transferencia (sq_instrumento) de cada plano de acao de TED, pela
-- carga mais recente do plano. E a unica ponte entre o SIAFI (NC, PF, NE) e o
-- TransfereGov: todos os modelos de TED leem daqui, para que a regra de
-- selecao seja a mesma em todos. Nulo em planos ainda nao firmados.
select distinct on (id_plano_acao) id_plano_acao, sq_instrumento as num_transf
from {{ ref("planos_acao_ted") }}
order by id_plano_acao, dt_ingest desc
