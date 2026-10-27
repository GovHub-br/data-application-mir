{{ config(materialized="table") }}

-- Etapas das metas do plano de acao de TED (API de TED, plano_acao_etapa).
select distinct
    on (id_etapa)
    {{ texto_sem_nan("id_etapa") }}::numeric::integer as id_etapa,
    {{ texto_sem_nan("id_meta") }}::numeric::integer as id_meta,
    {{ texto_sem_nan("nr_numero_etapa") }}::numeric::integer as nr_etapa,
    {{ texto_sem_nan("tx_nome_etapa") }} as no_etapa,
    {{ texto_sem_nan("tx_descricao_etapa") }} as ds_etapa,
    {{ texto_sem_nan("unidade_medida_etapa") }} as ds_unidade,
    {{ texto_sem_nan("nr_quantidade_etapa") }}::numeric as qt_etapa,
    {{ texto_sem_nan("vl_valor_unitario_etapa") }}::numeric as vl_unitario,
    {{ texto_sem_nan("dt_inicio_vigencia_etapa") }}::date as dt_inicio,
    {{ texto_sem_nan("dt_fim_vigencia_etapa") }}::date as dt_fim,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "planos_acao_etapa") }}
order by id_etapa, dt_ingest desc
