{{ config(materialized="table") }}

with
    justificativas_proposta_raw as (
        select
            nullif(id_proposta, '')::integer as id_proposta,
            caracterizacao_interesses_reci::text as caracterizacao_interesses_reci,
            publico_alvo::text as publico_alvo,
            problema_a_ser_resolvido::text as problema_a_ser_resolvido,
            resultados_esperados::text as resultados_esperados,
            relacao_proposta_objetivos_pro::text as relacao_proposta_objetivos_pro,
            capacidade_tecnica::text as capacidade_tecnica,
            justificativa::text as justificativa
        from {{ source("siconv", "justificativas_proposta") }}
    )

select *
from justificativas_proposta_raw
