{{ config(materialized="table") }}

with
    etapa_crono_fisico_raw as (
        select
            nullif(id_meta, '')::integer as id_meta,
            nullif(id_etapa, '')::integer as id_etapa,
            nullif(nr_etapa, '')::integer as nr_etapa,
            desc_etapa::text as desc_etapa,
            to_date(nullif(data_inicio_etapa, ''), 'DD/MM/YYYY') as data_inicio_etapa,
            to_date(nullif(data_fim_etapa, ''), 'DD/MM/YYYY') as data_fim_etapa,
            uf_etapa::text as uf_etapa,
            municipio_etapa::text as municipio_etapa,
            endereco_etapa::text as endereco_etapa,
            cep_etapa::text as cep_etapa,
            replace(nullif(qtd_etapa, ''), ',', '.')::numeric(15, 2) as qtd_etapa,
            und_fornecimento_etapa::text as und_fornecimento_etapa,
            replace(nullif(vl_etapa, ''), ',', '.')::numeric(15, 2) as vl_etapa
        from {{ source("siconv", "etapa_crono_fisico") }}
    )

select *
from etapa_crono_fisico_raw
