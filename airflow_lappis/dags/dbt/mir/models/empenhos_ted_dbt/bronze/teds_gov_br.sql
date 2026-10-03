{{ config(materialized="table") }}

{#
  TEDs raspados das páginas de transferências voluntárias do MIR no gov.br
  (teds_gov_br_ingest_mir_dag), só do retrato mais recente: cada execução grava
  a página inteira com o mesmo dt_ingest, e um TED que saiu da página não deve
  continuar valendo. Não há chave natural (a página às vezes repete o número/ano
  para TEDs diferentes), então a linha é identificada por página + ordem.
#}
with
    ultimo as (
        select *
        from {{ source("transfere_gov", "teds_gov_br") }}
        where
            dt_ingest
            = (select max(dt_ingest) from {{ source("transfere_gov", "teds_gov_br") }})
    )

select
    {{ texto_sem_nan("pagina") }} as pagina,
    {{ texto_sem_nan("ordem") }}::integer as ordem,
    {{ texto_sem_nan("numero_ted") }} as numero_ted,
    split_part({{ texto_sem_nan("numero_ted") }}, '/', 2)::integer as ano_ted,
    upper({{ texto_sem_nan("num_transf") }}) as num_transf,
    upper({{ texto_sem_nan("num_transf_alternativos") }}) as num_transf_alternativos,
    {{ texto_sem_nan("processo") }} as processo,
    {{ texto_sem_nan("parceiro") }} as parceiro,
    replace(replace({{ texto_sem_nan("valor") }}, '.', ''), ',', '.')::numeric(
        15, 2
    ) as valor,
    {{ texto_sem_nan("texto") }} as texto,
    {{ texto_sem_nan("url") }} as url,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from ultimo
