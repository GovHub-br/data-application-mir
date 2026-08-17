{{ config(materialized="table") }}

with
    emendas as (
        select *
        from {{ ref("numero_transferencia") }}
    ),

    proposta as (
        select
            id_proposta,
            modalidade
        from {{ ref("proposta") }}
    ),

    convenio_com_modalidade as (
        select distinct
            ltrim(trim(cast(cc.nr_convenio as text)), '0') as nr_convenio_clean,
            p.modalidade
        from {{ ref("convenios_consolidados") }} cc
        left join proposta p
            on cc.id_proposta = p.id_proposta
    ),

    ted as (
        select distinct
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_clean
        from {{ ref("ted_resumo_orcamentario") }}
    )

select
    e.*,

    coalesce(
        cm.nr_convenio_clean,
        t.num_transf_clean,
        et.numero_extraido
    ) as numero_instrumento,

    case
        when cm.nr_convenio_clean is not null then coalesce(cm.modalidade, 'CONVENIO')
        when t.num_transf_clean is not null then 'TED'
        when et.tipo_extraido ilike 'TERMO%' then 'TERMO DE FOMENTO'
        when et.tipo_extraido ilike 'CONV%' then 'CONVENIO'
        when et.tipo_extraido ilike 'TED' then 'TED'
        else null
    end as tipo_instrumento,

    (
        cm.nr_convenio_clean is null
        and t.num_transf_clean is null
        and et.tipo_extraido is not null
    ) as instrumento_identificado_por_texto

from emendas e
left join convenio_com_modalidade cm
    on ltrim(trim(cast(e.numero_transferencia as text)), '0') = cm.nr_convenio_clean
left join ted t
    on ltrim(trim(cast(e.numero_transferencia as text)), '0') = t.num_transf_clean
left join lateral (
    select
        (regexp_match(
            coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, ''),
            '(?i)(TERMO\s+DE\s+FOMENTO|CONVENIO|CONVÊNIO|TED)\s*(?:Nº|N°|N|º|°)?\s*(\d{4,7})'
        ))[1] as tipo_extraido,
        ltrim((regexp_match(
            coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, ''),
            '(?i)(TERMO\s+DE\s+FOMENTO|CONVENIO|CONVÊNIO|TED)\s*(?:Nº|N°|N|º|°)?\s*(\d{4,7})'
        ))[2], '0') as numero_extraido
) et on true