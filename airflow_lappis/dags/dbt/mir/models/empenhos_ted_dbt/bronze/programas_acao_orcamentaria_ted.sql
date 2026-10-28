{{ config(materialized="table") }}

-- Acoes orcamentarias dos programas de TED (API de TED,
-- programa_acao_orcamentaria). Sem chave na fonte; substituida a cada carga.
select distinct
    {{ texto_sem_nan("id_programa") }}::numeric::integer as id_programa,
    {{ texto_sem_nan("tx_codigo_acao_orcamentaria") }} as cd_acao_orcamentaria,
    {{ texto_sem_nan("tx_descricao_acao_orcamentaria") }} as ds_acao_orcamentaria
from {{ source("transfere_gov", "programas_acao_orcamentaria") }}
