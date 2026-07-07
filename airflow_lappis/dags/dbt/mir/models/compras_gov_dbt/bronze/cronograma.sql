{{ config(materialized="table") }}

with
    cronograma_raw as (
        select
            nullif(id, '')::integer as id,
            contrato_id::text as contrato_id,
            tipo::text as tipo,
            numero::text as numero,
            receita_despesa::text as receita_despesa,
            observacao::text as observacao,
            nullif(mesref, '')::integer as mesref,
            nullif(anoref, '')::integer as anoref,
            case
                when vencimento is not null and vencimento::text ~ '^\d{4}-\d{2}-\d{2}$'
                then vencimento::date
            end as vencimento,
            retroativo::text as retroativo,
            replace(replace(nullif(valor, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as valor,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("compras_gov", "cronograma") }}
    )

select *
from cronograma_raw