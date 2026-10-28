{{ config(materialized="table") }}

-- Eventos contabeis das notas de credito de TED (API de TED, evento): PTRES,
-- fonte, plano interno e natureza de despesa por NC. A fonte nao tem chave; a
-- ingestao substitui a tabela inteira a cada carga.
select
    {{ texto_sem_nan("id_nota") }}::numeric::integer as id_nota,
    {{ texto_sem_nan("cd_evento") }} as cd_evento,
    {{ texto_sem_nan("cd_ptres_evento") }} as cd_ptres,
    {{ texto_sem_nan("cd_fonte_recurso_evento") }} as cd_fonte_recurso,
    {{ texto_sem_nan("cd_plano_interno_evento") }} as cd_plano_interno,
    {{ texto_sem_nan("vl_evento") }}::numeric as vl_evento,
    {{ texto_sem_nan("cd_ug_responsavel_evento") }} as cd_ug_responsavel,
    {{ texto_sem_nan("codigo_natureza") }} as cd_natureza_despesa,
    {{ texto_sem_nan("descricao_natureza") }} as ds_natureza_despesa,
    {{ texto_sem_nan("nome_esfera_orcamentaria") }} as no_esfera_orcamentaria,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "eventos_nota_credito") }}
