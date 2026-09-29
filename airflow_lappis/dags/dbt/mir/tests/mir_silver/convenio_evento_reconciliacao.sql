-- Falha se a quantidade de eventos de algum tipo divergir da bronze dos
-- convenios do MIR depois das limpezas documentadas: historico de situacao
-- sem repeticoes (uma linha por convenio x data x situacao) e prorrogacoes
-- sem linhas identicas.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    bronze as (
        select 'Mudança de situação' as tipo_evento, count(*) as qtd
        from
            (
                select nr_convenio, dia_historico_sit, historico_sit, cod_historico_sit
                from {{ ref("historico_situacao") }}
                where nr_convenio in (select nr_convenio from mir)
                group by nr_convenio, dia_historico_sit, historico_sit, cod_historico_sit
            ) as h
        union all
        select 'Termo aditivo', count(*)
        from {{ ref("termo_aditivo") }}
        where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Prorrogação de ofício', count(*)
        from
            (
                select distinct *
                from {{ ref("prorroga_oficio") }}
                where nr_convenio in (select nr_convenio from mir)
            ) as p
        union all
        select 'Solicitação de alteração', count(*)
        from {{ ref("solicitacao_alteracao") }}
        where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Solicitação de rendimento', count(*)
        from {{ ref("solicitacao_rendimento_aplicacao") }}
        where nr_convenio in (select nr_convenio from mir)
    ),

    silver as (
        select tipo_evento, count(*) as qtd
        from {{ ref("convenio_evento") }}
        group by tipo_evento
    )

select b.tipo_evento, b.qtd as qtd_bronze, s.qtd as qtd_silver
from bronze as b
left join silver as s on s.tipo_evento = b.tipo_evento
where coalesce(s.qtd, 0) <> b.qtd
