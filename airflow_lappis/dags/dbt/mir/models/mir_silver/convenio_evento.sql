{{ config(materialized="table") }}

-- Eventos administrativos dos convenios do MIR, uma linha por evento.
-- Limpezas da origem:
-- * historico_situacao traz linhas repetidas a cada ingestao, as vezes com
-- dias_historico_sit recalculado: fica uma linha por convenio x data x
-- situacao, com o maior numero de dias;
-- * prorroga_oficio traz linhas identicas e reuso de nr_prorroga para
-- prorrogacoes distintas: a chave inclui a data de inicio.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    historico as (
        select
            nr_convenio,
            dia_historico_sit,
            historico_sit,
            cod_historico_sit,
            max(dias_historico_sit) as dias_historico_sit
        from {{ ref("historico_situacao") }}
        group by nr_convenio, dia_historico_sit, historico_sit, cod_historico_sit
    ),

    prorrogacoes as (select distinct * from {{ ref("prorroga_oficio") }}),

    eventos as (
        select
            nr_convenio,
            'Mudança de situação' as tipo_evento,
            concat_ws(
                '|', dia_historico_sit, cod_historico_sit, historico_sit
            ) as chave_origem,
            dia_historico_sit as data_evento,
            historico_sit as situacao,
            null::text as descricao,
            null::numeric as valor,
            null::numeric as valor_aprovado,
            dias_historico_sit as dias,
            null::date as data_fim_nova
        from historico

        union all

        select
            nr_convenio,
            'Termo aditivo' as tipo_evento,
            numero_ta as chave_origem,
            dt_assinatura_ta as data_evento,
            null::text as situacao,
            tipo_ta as descricao,
            vl_global_ta as valor,
            null::numeric as valor_aprovado,
            null::integer as dias,
            dt_fim_ta as data_fim_nova
        from {{ ref("termo_aditivo") }}

        union all

        select
            nr_convenio,
            'Prorrogação de ofício' as tipo_evento,
            concat_ws('|', nr_prorroga, dt_inicio_prorroga) as chave_origem,
            dt_assinatura_prorroga as data_evento,
            sit_prorroga as situacao,
            null::text as descricao,
            null::numeric as valor,
            null::numeric as valor_aprovado,
            dias_prorroga as dias,
            dt_fim_prorroga as data_fim_nova
        from prorrogacoes

        union all

        select
            nr_convenio,
            'Solicitação de alteração' as tipo_evento,
            id_solicitacao::text as chave_origem,
            data_solicitacao as data_evento,
            situacao_solicitacao as situacao,
            objeto_solicitacao as descricao,
            null::numeric as valor,
            null::numeric as valor_aprovado,
            null::integer as dias,
            null::date as data_fim_nova
        from {{ ref("solicitacao_alteracao") }}

        union all

        select
            nr_convenio,
            'Solicitação de rendimento' as tipo_evento,
            id_solicitacao_rend_aplicacao::text as chave_origem,
            data_solicitacao_rend_aplicacao as data_evento,
            status_solicitacao_rend_aplicacao as situacao,
            null::text as descricao,
            valor_solicitacao_rend_aplicacao as valor,
            valor_aprovado_solicitacao_rend_aplicacao as valor_aprovado,
            null::integer as dias,
            null::date as data_fim_nova
        from {{ ref("solicitacao_rendimento_aplicacao") }}
    )

select
    md5(concat_ws('|', e.tipo_evento, e.nr_convenio, e.chave_origem)) as id_evento,
    e.nr_convenio,
    e.tipo_evento,
    e.data_evento,
    e.situacao,
    e.descricao,
    e.valor,
    e.valor_aprovado,
    e.dias,
    e.data_fim_nova
from eventos as e
inner join mir on mir.nr_convenio = e.nr_convenio
