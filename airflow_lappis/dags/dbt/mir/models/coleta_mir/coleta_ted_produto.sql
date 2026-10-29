{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 5.2 do formulário de TEDs: os produtos previstos no plano
  de trabalho de cada TED de coleta_ted, para o gestor escolher o produto ao qual liga a
  atividade que executou.

  Uma linha por meta e uma por etapa da meta. A meta é o produto pactuado; as etapas
  são as ações previstas dentro dela, com unidade, quantidade e valor (a meta não traz
  esses três). id_origem é a chave estável da linha na fonte: nr_meta e nr_etapa são a
  numeração que o gestor vê no plano e podem se repetir, então a resposta do Coleta deve
  apontar para id_origem.
#}
with
    meta as (
        select m.*
        from {{ ref("planos_acao_meta_ted") }} as m
        join {{ ref("coleta_ted") }} as c on c.id_plano_acao = m.id_plano_acao
    ),

    linhas as (
        select
            'meta:' || id_meta as id_origem,
            id_plano_acao,
            'meta' as tp_nivel,
            cast(null as text) as id_origem_pai,
            nr_meta,
            cast(null as integer) as nr_etapa,
            no_meta as no_item,
            ds_meta as ds_item,
            ds_unidade,
            qt_meta as qt_prevista,
            vl_unitario,
            dt_inicio,
            dt_fim,
            dt_ingest as dt_atualizacao
        from meta

        union all

        select
            'etapa:' || e.id_etapa as id_origem,
            m.id_plano_acao,
            'etapa' as tp_nivel,
            'meta:' || m.id_meta as id_origem_pai,
            m.nr_meta,
            e.nr_etapa,
            e.no_etapa as no_item,
            e.ds_etapa as ds_item,
            e.ds_unidade,
            e.qt_etapa as qt_prevista,
            e.vl_unitario,
            e.dt_inicio,
            e.dt_fim,
            least(m.dt_ingest, e.dt_ingest) as dt_atualizacao
        from {{ ref("planos_acao_etapa_ted") }} as e
        join meta as m on m.id_meta = e.id_meta
    )

select
    id_origem::text as id_origem,
    id_plano_acao::integer as id_plano_acao,
    tp_nivel::text as tp_nivel,
    id_origem_pai::text as id_origem_pai,
    nr_meta::integer as nr_meta,
    nr_etapa::integer as nr_etapa,
    no_item::text as no_item,
    ds_item::text as ds_item,
    ds_unidade::text as ds_unidade,
    qt_prevista::numeric as qt_prevista,
    vl_unitario::numeric as vl_unitario,
    dt_inicio::date as dt_inicio,
    dt_fim::date as dt_fim,
    dt_atualizacao::timestamptz as dt_atualizacao
from linhas
