{{ config(materialized="table") }}

with
    senadores_raw as (
        select
            parlamentar_id::integer as parlamentar_id,
            partido__codigopartido::text as codigo_partido,
            partido__siglapartido::text as sigla_partido,
            partido__nomepartido::text as nome_partido,
            case
                when lower(trim(datafiliacao::text)) in ('', 'nan', 'null') then null
                else datafiliacao::timestamptz
            end as data_filiacao,
            case
                when lower(trim(datadesfiliacao::text)) in ('', 'nan', 'null') then null
                else datadesfiliacao::timestamptz
            end as data_desfiliação,
            fonte:: text as fonte,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("senado_federal", "senadores_historico") }}
    ),

    senadores_filtrados as (
        select *
        from senadores_raw
        where (data_filiacao is not null and data_filiacao >= '1995-01-01'::timestamptz) -- data confiável
    )

select *
from senadores_filtrados
