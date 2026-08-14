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
    ),

    termo_fomento as (
        select distinct 
            ltrim(trim(cast(nr_convenio as text)), '0') as nr_convenio_clean
        from {{ ref("termo_fomento_consolidado") }}
    )

select
    e.*,
    coalesce(
        cm.nr_convenio_clean, 
        tf.nr_convenio_clean, 
        t.num_transf_clean
    ) as numero_instrumento,

    case
        when cm.nr_convenio_clean is not null then coalesce(cm.modalidade, 'CONVENIO')
        when tf.nr_convenio_clean is not null then 'TERMO DE FOMENTO'
        when t.num_transf_clean is not null then 'TED'
        when (coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, '')) ilike '%TERMO DE FOMENTO%' then 'TERMO DE FOMENTO'
        when (coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, '')) ilike '%CONVENIO%' 
          or (coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, '')) ilike '%CONVÊNIO%' then 'CONVENIO'
        when (coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, '')) ilike '%TED%' then 'TED'
        else null
    end as tipo_instrumento

from emendas e
left join convenio_com_modalidade cm
    on ltrim(
        coalesce(
            nullif(trim(cast(e.numero_transferencia as text)), ''),
            nullif(trim(cast(e.numero_transferencia as text)), '0'),
            substring(
                coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, '')
                from '(?i)(?:TERMO\s+DE\s+FOMENTO|CONVENIO|TED)\s*(?:Nº|N°|N|º|°)?\s*(\d{4,7})'
            )
        ), 
        '0'
    ) = cm.nr_convenio_clean

left join termo_fomento tf
    on ltrim(
        coalesce(
            nullif(trim(cast(e.numero_transferencia as text)), ''),
            nullif(trim(cast(e.numero_transferencia as text)), '0'),
            substring(
                coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, '')
                from '(?i)(?:TERMO\s+DE\s+FOMENTO|CONVENIO|TED)\s*(?:Nº|N°|N|º|°)?\s*(\d{4,7})'
            )
        ), 
        '0'
    ) = tf.nr_convenio_clean

left join ted t
    on ltrim(
        coalesce(
            nullif(trim(cast(e.numero_transferencia as text)), ''),
            nullif(trim(cast(e.numero_transferencia as text)), '0'),
            substring(
                coalesce(e.ne_info_complementar, '') || ' ' || coalesce(e.ne_ccor_descricao, '') || ' ' || coalesce(e.doc_observacao, '')
                from '(?i)(?:TERMO\s+DE\s+FOMENTO|CONVENIO|TED)\s*(?:Nº|N°|N|º|°)?\s*(\d{4,7})'
            )
        ), 
        '0'
    ) = t.num_transf_clean