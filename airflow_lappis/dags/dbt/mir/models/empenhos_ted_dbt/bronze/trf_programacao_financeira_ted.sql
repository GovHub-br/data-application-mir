{{ config(materialized="table") }}

-- TRF das programacoes financeiras de TED (API de TED, trf): vinculacao,
-- fonte, categoria de gasto e valor. Sem chave na fonte; substituida a cada
-- carga.
select
    {{ texto_sem_nan("id_programacao") }}::numeric::integer as id_programacao,
    {{ texto_sem_nan("cd_vinculacao_trf") }} as cd_vinculacao,
    {{ texto_sem_nan("cd_fonte_recurso_trf") }} as cd_fonte_recurso,
    {{ texto_sem_nan("cd_categoria_gasto_trf") }} as cd_categoria_gasto,
    {{ texto_sem_nan("vl_valor_trf") }}::numeric as vl_trf,
    {{ texto_sem_nan("cd_situacao_contabil_trf") }} as cd_situacao_contabil,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "trf_programacao_financeira") }}
