{{ config(materialized="table") }}

-- Metas do plano de acao de TED (API de TED, plano_acao_meta). Base da lista
-- de metas/produtos do item 5.2 do Coleta MIR para TEDs.
select distinct
    on (id_meta)
    {{ texto_sem_nan("id_meta") }}::numeric::integer as id_meta,
    {{ texto_sem_nan("id_plano_acao") }}::numeric::integer as id_plano_acao,
    {{ texto_sem_nan("nr_numero_meta") }}::numeric::integer as nr_meta,
    {{ texto_sem_nan("tx_nome_meta") }} as no_meta,
    {{ texto_sem_nan("tx_descricao_meta") }} as ds_meta,
    {{ texto_sem_nan("tp_unidade_meta") }} as ds_unidade,
    {{ texto_sem_nan("nr_quantidade_meta") }}::numeric as qt_meta,
    {{ texto_sem_nan("vl_valor_unitario_meta") }}::numeric as vl_unitario,
    {{ texto_sem_nan("dt_inicio_vigencia_meta") }}::date as dt_inicio,
    {{ texto_sem_nan("dt_fim_vigencia_meta") }}::date as dt_fim,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "planos_acao_meta") }}
order by id_meta, dt_ingest desc
