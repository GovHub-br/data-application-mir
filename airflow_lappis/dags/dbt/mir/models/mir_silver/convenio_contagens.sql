{{ config(materialized="table") }}

-- Contagens de metas fisicas e licitacoes por convenio do MIR. O gold atual so
-- usa esses dados como contagens; o detalhe por meta ou licitacao vira fato
-- propria quando algum painel precisar. Marcacoes que dependem da data de hoje
-- (meta expirada, dias sem desembolso) nao ficam aqui: a silver guarda as datas
-- e o gold ou o BI calcula a marcacao com a data de referencia explicita.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    metas as (
        select
            nr_convenio,
            count(*) as qtd_metas,
            sum(vl_meta) as valor_metas,
            min(data_fim_meta) as data_fim_primeira_meta
        from {{ ref("meta_crono_fisico") }}
        where nr_convenio in (select nr_convenio from mir)
        group by nr_convenio
    ),

    licitacoes as (
        select
            nr_convenio,
            count(*) as qtd_licitacoes,
            sum(valor_licitacao) as valor_licitado
        from {{ ref("licitacao") }}
        where nr_convenio in (select nr_convenio from mir)
        group by nr_convenio
    ),

    desembolsos as (
        select nr_convenio, max(dt_ult_desembolso) as data_ultimo_desembolso
        from {{ ref("desembolso") }}
        where nr_convenio in (select nr_convenio from mir)
        group by nr_convenio
    )

select
    c.nr_convenio,
    coalesce(m.qtd_metas, 0) as qtd_metas,
    coalesce(m.valor_metas, 0) as valor_metas,
    m.data_fim_primeira_meta,
    coalesce(l.qtd_licitacoes, 0) as qtd_licitacoes,
    coalesce(l.valor_licitado, 0) as valor_licitado,
    d.data_ultimo_desembolso
from mir as c
left join metas as m on m.nr_convenio = c.nr_convenio
left join licitacoes as l on l.nr_convenio = c.nr_convenio
left join desembolsos as d on d.nr_convenio = c.nr_convenio
