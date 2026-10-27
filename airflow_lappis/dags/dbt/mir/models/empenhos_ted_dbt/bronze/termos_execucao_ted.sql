{{ config(materialized="table") }}

-- Termo de execucao do TED (API de TED, termo_execucao): processo SEI e datas
-- de assinatura/divulgacao. Alimenta Numero SEI e Data de celebracao (Bloco 1)
-- no contrato do Coleta MIR.
select distinct
    on (id_termo)
    {{ texto_sem_nan("id_termo") }}::numeric::integer as id_termo,
    {{ texto_sem_nan("id_plano_acao") }}::numeric::integer as id_plano_acao,
    {{ texto_sem_nan("tx_situacao_termo") }} as ds_situacao,
    {{ texto_sem_nan("tx_num_processo_sei") }} as nr_processo_sei,
    {{ texto_sem_nan("dt_assinatura_termo") }}::date as dt_assinatura,
    {{ texto_sem_nan("dt_divulgacao_termo") }}::date as dt_divulgacao,
    {{ texto_sem_nan("in_minuta_padrao") }}::boolean as in_minuta_padrao,
    {{ texto_sem_nan("tx_numero_ns_termo") }} as nr_ns,
    {{ texto_sem_nan("dt_recebimento_termo") }}::date as dt_recebimento,
    {{ texto_sem_nan("dt_efetivacao_termo") }}::date as dt_efetivacao,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("transfere_gov", "termos_execucao") }}
order by id_termo, dt_ingest desc
