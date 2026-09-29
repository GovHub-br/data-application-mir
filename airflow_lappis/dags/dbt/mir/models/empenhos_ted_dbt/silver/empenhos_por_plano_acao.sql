{{ config(materialized="table") }}

-- A cascata de extracao de num_transf foi movida para
-- mir_silver.ted_ne_transferencia (etapa 3 da remodelagem). Este modelo so
-- resolve o plano de acao pela ponte num_transf_n_plano_acao, com a mesma saida
-- de antes, ate ser removido na etapa 5.
with
    planos_de_acao as (
        select * from {{ ref("num_transf_n_plano_acao") }} where plano_acao is not null
    )

select distinct er.*, pa.plano_acao::integer as plano_acao, pa.num_transf as num_transf_pa
from {{ ref("ted_ne_transferencia") }} as er
left join planos_de_acao as pa on er.num_transf = cast(pa.num_transf as text)
