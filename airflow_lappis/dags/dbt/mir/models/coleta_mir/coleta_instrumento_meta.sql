{{ config(materialized="table") }}

-- Metas (e etapas, so TED) do plano de trabalho de cada instrumento do
-- contrato do Coleta MIR. Linha da meta: nr_etapa nulo.
with
    ted_plano as (
        select
            'ted:' || id_instrumento::text as chave_instrumento,
            plano_acao::integer as id_plano_acao
        from {{ ref("ted_resumo_orcamentario") }}
        where tipo_instrumento = 'TED' and plano_acao is not null
    ),

    ted_metas as (
        select
            tp.chave_instrumento,
            m.nr_meta,
            cast(null as integer) as nr_etapa,
            m.no_meta,
            m.ds_meta,
            m.qt_meta,
            m.ds_unidade,
            cast(null as text) as sg_uf,
            cast(null as text) as no_municipio,
            m.dt_inicio,
            m.dt_fim
        from {{ ref("planos_acao_meta_ted") }} as m
        inner join ted_plano as tp on tp.id_plano_acao = m.id_plano_acao
    ),

    ted_etapas as (
        select
            tp.chave_instrumento,
            m.nr_meta,
            -- nr_etapa da API se repete dentro da mesma meta (etapas distintas
            -- com o mesmo numero); renumera em sequencia por meta, na ordem
            -- (nr_etapa original, id_etapa), para manter o grao unico.
            cast(
                row_number() over (
                    partition by tp.chave_instrumento, m.nr_meta
                    order by e.nr_etapa, e.id_etapa
                ) as integer
            ) as nr_etapa,
            e.no_etapa as no_meta,
            e.ds_etapa as ds_meta,
            e.qt_etapa as qt_meta,
            e.ds_unidade,
            cast(null as text) as sg_uf,
            cast(null as text) as no_municipio,
            e.dt_inicio,
            e.dt_fim
        from {{ ref("planos_acao_etapa_ted") }} as e
        inner join {{ ref("planos_acao_meta_ted") }} as m on m.id_meta = e.id_meta
        inner join ted_plano as tp on tp.id_plano_acao = m.id_plano_acao
    ),

    convenio_metas as (
        select
            ci.chave as chave_instrumento,
            mc.nr_meta::integer as nr_meta,
            cast(null as integer) as nr_etapa,
            ('Meta ' || mc.nr_meta::text) as no_meta,
            mc.desc_meta::text as ds_meta,
            mc.qtd_meta::numeric as qt_meta,
            mc.und_fornecimento_meta::text as ds_unidade,
            nullif(mc.uf_meta::text, '') as sg_uf,
            nullif(mc.municipio_meta::text, '') as no_municipio,
            mc.data_inicio_meta::date as dt_inicio,
            mc.data_fim_meta::date as dt_fim
        from {{ ref("meta_crono_fisico") }} as mc
        inner join
            {{ ref("coleta_instrumento") }} as ci
            on ci.tp_instrumento in ('convenio', 'termo_fomento')
            and ci.nr_instrumento = mc.nr_convenio::text
    )

select *
from ted_metas
union all
select *
from ted_etapas
union all
select *
from convenio_metas
