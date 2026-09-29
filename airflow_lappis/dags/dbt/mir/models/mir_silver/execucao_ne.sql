{{ config(materialized="table") }}

-- Nucleo da execucao orcamentaria do MIR, no grao da linha de empenho do
-- ppa_tesouro. Todas as NEs de emenda e de TED ja estao no ppa_tesouro, entao
-- os valores vem so daqui: uma NE nunca e somada duas vezes. Os vinculos e a
-- origem do recurso sao resolvidos no grao da NE e replicados nas linhas.
with
    empenhos as (
        select *
        from {{ ref("ppa_tesouro") }}
        -- ne_ccor = '-9' sao linhas de dotacao, sem NE real
        where ne_ccor <> '-9'
    ),

    -- Cada NE pertence a no maximo uma emenda no tg_emendas
    emendas as (
        select distinct ne_ccor, autor_emendas_orcamento as codigo_emenda
        from {{ ref("tg_emendas") }}
    ),

    ted as (select * from {{ ref("vinculo_ne_ted") }}),

    convenio as (select * from {{ ref("vinculo_ne_convenio") }})

select
    e.id_hash as id_execucao_ne,
    e.ne_ccor,

    -- Datas: 000/AAAA e inscricao de restos a pagar do exercicio AAAA
    case
        when e.emissao_dia ~ '^\d{2}/\d{2}/\d{4}$'
        then to_date(e.emissao_dia, 'DD/MM/YYYY')
        when e.emissao_dia ~ '^000/\d{4}$'
        then make_date(right(e.emissao_dia, 4)::integer, 1, 1)
    end as data_emissao,
    coalesce(e.emissao_dia ~ '^000/\d{4}$', false) as inscricao_rap,
    e.ne_ccor_ano_emissao,

    -- Unidades gestoras
    left(e.ne_ccor, 6) as ug_emitente_codigo,
    e.ug_responsavel_codigo,
    e.ug_responsavel_nome,

    -- Classificacao orcamentaria
    e.programa_governo,
    e.programa_governo_descricao,
    e.acao_governo,
    e.acao_governo_descricao,
    e.ptres,
    e.plano_orcamentario_codigo_uo,
    e.plano_orcamentario_codigo_funcao,
    e.plano_orcamentario_codigo_subfuncao,
    e.plano_orcamentario_codigo_programa,
    e.plano_orcamentario_codigo_acao,
    e.plano_orcamentario_codigo_po,
    e.plano_orcamentario_nome,
    e.natureza_despesa,
    e.natureza_despesa_descricao,
    e.grupo_despesa,
    e.grupo_despesa_desc,
    e.fonte_recursos_detalhada,
    e.fonte_recursos_detalhada_descricao,
    e.resultado_eof_codigo,
    e.resultado_eof_nome,

    -- Favorecido
    e.ne_ccor_favorecido as favorecido_documento,
    e.ne_ccor_favorecido_descricao as favorecido_nome,

    -- Textos de origem dos vinculos (mantidos para auditoria)
    e.ne_num_processo,
    e.ne_info_complementar,
    e.ne_ccor_descricao,
    e.doc_observacao,

    -- Origem do recurso
    em.codigo_emenda,
    case
        when em.codigo_emenda is not null then 'Emenda' else 'Recurso próprio'
    end as origem_recurso,

    -- Instrumento: TED tem precedencia; senao o convenio escolhido em vinculo_ne_convenio
    case
        when t.ne_ccor is not null
        then 'TED'
        when c.nr_convenio is not null
        then 'SICONV'
        else 'Não identificado'
    end as sistema_instrumento,
    case
        when t.ne_ccor is not null
        then t.id_plano_acao::text
        when c.nr_convenio is not null
        then c.nr_convenio
    end as nr_instrumento,
    t.num_transf,
    case
        when t.ne_ccor is not null
        then 'ted: ' || t.metodo_ted
        when c.nr_convenio is not null and c.desempate_processo
        then 'convenio: ' || c.fonte_vinculo || ' (desempate por processo)'
        when c.nr_convenio is not null
        then 'convenio: ' || c.fonte_vinculo
        when c.qtd_convenios > 1
        then 'ambiguo'
        else 'nao_encontrado'
    end as metodo_vinculo,

    -- Valores
    e.despesas_empenhadas,
    e.despesas_liquidadas,
    e.despesas_pagas,
    e.restos_a_pagar_inscritos,
    e.restos_a_pagar_pagos,

    e.dt_ingest
from empenhos as e
left join emendas as em on em.ne_ccor = e.ne_ccor
left join ted as t on t.ne_ccor = e.ne_ccor
left join convenio as c on c.ne_ccor = e.ne_ccor
