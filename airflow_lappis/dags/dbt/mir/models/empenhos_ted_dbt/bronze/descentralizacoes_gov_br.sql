{{ config(materialized="table") }}

{#
  Descentralizações de crédito sem TED (tedinhos) raspadas das páginas de
  transferências voluntárias do MIR no gov.br (teds_gov_br_ingest_mir_dag): blocos
  "Descentralização de Crédito ... Processo: ... Objeto: ... R$ ...". Só o retrato mais
  recente, como em teds_gov_br; a linha é identificada por página + ordem.
#}
with
    ultimo as (
        select *
        from {{ source("transfere_gov", "descentralizacoes_gov_br") }}
        where
            dt_ingest = (
                select max(dt_ingest)
                from {{ source("transfere_gov", "descentralizacoes_gov_br") }}
            )
    )

select
    {{ texto_sem_nan("pagina") }} as pagina,
    {{ texto_sem_nan("ordem") }}::integer as ordem,
    {{ texto_sem_nan("processo") }} as processo,
    {{ texto_sem_nan("parceiro") }} as parceiro,
    {{ texto_sem_nan("objeto") }} as objeto,
    replace(replace({{ texto_sem_nan("valor") }}, '.', ''), ',', '.')::numeric(
        15, 2
    ) as valor,
    {{ texto_sem_nan("texto") }} as texto,
    {{ texto_sem_nan("url") }} as url,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from ultimo
