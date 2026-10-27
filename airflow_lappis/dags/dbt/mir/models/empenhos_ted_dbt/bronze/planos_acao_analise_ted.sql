{{ config(materialized="table") }}

-- Analises do plano de acao de TED (API de TED, plano_acao_analise).
select distinct
    on (id_analise)
    {{ texto_sem_nan("id_analise") }}::numeric::integer as id_analise,
    {{ texto_sem_nan("id_plano_acao") }}::numeric::integer as id_plano_acao,
    {{ texto_sem_nan("tx_justificativa_analise") }} as ds_justificativa,
    {{ texto_sem_nan("resultado_analise") }} as ds_resultado,
    {{ texto_sem_nan("tx_situacao_analise") }} as ds_situacao,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "planos_acao_analise") }}
order by id_analise, dt_ingest desc
