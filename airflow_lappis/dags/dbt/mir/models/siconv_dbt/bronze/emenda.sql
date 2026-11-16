{{ config(materialized="table") }}

with
    emenda_raw as (
        select
            nullif(id_proposta, '')::integer as id_proposta,
            nullif(qualif_proponente, '')::text as qualif_proponente,
            cod_programa_emenda::text as cod_programa_emenda,
            -- Linhas antigas trazem o texto 'null' no lugar do número.
            nullif(nullif(nr_emenda, ''), 'null')::text as nr_emenda,
            nullif(nome_parlamentar, '')::text as nome_parlamentar,
            nullif(beneficiario_emenda, '')::text as beneficiario_emenda,
            nullif(ind_impositivo, '')::text as ind_impositivo,
            nullif(tipo_parlamentar, '')::text as tipo_parlamentar,
            replace(nullif(valor_repasse_proposta_emenda, ''), ',', '.')::numeric(
                15, 2
            ) as valor_repasse_proposta_emenda,
            replace(nullif(valor_repasse_emenda, ''), ',', '.')::numeric(
                15, 2
            ) as valor_repasse_emenda
        from {{ source("siconv", "emenda") }}
    )

select *
from emenda_raw
