{{ config(materialized="table") }}

-- Beneficiarios (orgaos, por codigo Siorg) dos programas de TED (API de TED,
-- programa_beneficiario). Sem chave na fonte; substituida a cada carga.
select
    {{ texto_sem_nan("id_programa") }}::numeric::integer as id_programa,
    {{ texto_sem_nan("tx_codigo_siorg") }} as cd_siorg,
    {{ texto_sem_nan("tx_nome_beneficiario") }} as no_beneficiario,
    {{ texto_sem_nan("vl_valor_beneficiario") }}::numeric as vl_beneficiario,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "programas_beneficiario") }}
