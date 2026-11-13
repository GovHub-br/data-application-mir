{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 5.2 do formulário de convênios: os produtos previstos no
  plano de trabalho de cada convênio de coleta_convenio, para o gestor escolher o produto
  ao qual liga a atividade que executou. Mesmo desenho de coleta_ted_produto.

  Uma linha por meta e uma por etapa da meta, do cronograma físico do siconv. A meta liga
  ao convênio pela proposta: no siconv o nr_convenio da meta fica nulo em boa parte das
  propostas. id_origem é a chave estável da linha na fonte: nr_meta e nr_etapa são a
  numeração que o gestor vê no plano, então a resposta do Coleta deve apontar para
  id_origem.

  A meta do siconv só tem descrição, sem nome: no_item fica nulo. vl_item é o valor total
  previsto da meta ou da etapa, não o unitário.
#}
with
    meta as (
        select m.*, c.nr_convenio as nr_convenio_coleta
        from {{ ref("meta_crono_fisico") }} as m
        inner join {{ ref("coleta_convenio") }} as c on c.id_proposta = m.id_proposta
    ),

    linhas as (
        select
            'meta:' || id_meta as id_origem,
            nr_convenio_coleta as nr_convenio,
            'meta' as tp_nivel,
            cast(null as text) as id_origem_pai,
            nr_meta,
            cast(null as integer) as nr_etapa,
            desc_meta as ds_item,
            und_fornecimento_meta as ds_unidade,
            qtd_meta as qt_prevista,
            vl_meta as vl_item,
            data_inicio_meta as dt_inicio,
            data_fim_meta as dt_fim,
            uf_meta as sg_uf,
            municipio_meta as no_municipio
        from meta

        union all

        select
            'etapa:' || e.id_etapa as id_origem,
            m.nr_convenio_coleta as nr_convenio,
            'etapa' as tp_nivel,
            'meta:' || m.id_meta as id_origem_pai,
            m.nr_meta,
            e.nr_etapa,
            e.desc_etapa as ds_item,
            e.und_fornecimento_etapa as ds_unidade,
            e.qtd_etapa as qt_prevista,
            e.vl_etapa as vl_item,
            e.data_inicio_etapa as dt_inicio,
            e.data_fim_etapa as dt_fim,
            e.uf_etapa as sg_uf,
            e.municipio_etapa as no_municipio
        from {{ ref("etapa_crono_fisico") }} as e
        inner join meta as m on m.id_meta = e.id_meta
    )

select
    id_origem::text as id_origem,
    nr_convenio::text as nr_convenio,
    tp_nivel::text as tp_nivel,
    id_origem_pai::text as id_origem_pai,
    nr_meta::integer as nr_meta,
    nr_etapa::integer as nr_etapa,
    cast(null as text) as no_item,
    nullif(trim(ds_item), '')::text as ds_item,
    nullif(trim(ds_unidade), '')::text as ds_unidade,
    qt_prevista::numeric as qt_prevista,
    vl_item::numeric(15, 2) as vl_item,
    dt_inicio::date as dt_inicio,
    dt_fim::date as dt_fim,
    nullif(trim(sg_uf), '')::text as sg_uf,
    nullif(trim(no_municipio), '')::text as no_municipio
from linhas
