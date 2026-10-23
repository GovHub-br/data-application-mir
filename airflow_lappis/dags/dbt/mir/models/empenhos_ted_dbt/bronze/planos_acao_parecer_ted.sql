{{ config(materialized="table") }}

-- Pareceres do plano de acao de TED (API de TED, plano_acao_parecer).
select distinct
    on (id_parecer)
    {{ texto_sem_nan("id_parecer") }}::numeric::integer as id_parecer,
    {{ texto_sem_nan("id_plano_acao") }}::numeric::integer as id_plano_acao,
    {{ texto_sem_nan("tp_analise_parecer") }} as tp_analise,
    {{ texto_sem_nan("resultado_parecer") }} as ds_resultado,
    {{ texto_sem_nan("tx_parecer") }} as ds_parecer,
    {{ texto_sem_nan("plano_acao_hist_fk") }}::numeric::integer as id_plano_acao_hist,
    {{ texto_sem_nan("dt_data_parecer") }}::date as dt_parecer,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "planos_acao_parecer") }}
order by id_parecer, dt_ingest desc
