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

    convenio as (select * from {{ ref("vinculo_ne_convenio") }}),

    -- NE gerada pela rotina de transferencia de saldo (NSSALDO): nao traz o
    -- numero do instrumento, mas cita o empenho de origem ("EMPENHO DE ORIGEM:
    -- 810008/2024NE000092"). A NE de origem e achada pela UG (6 primeiros
    -- caracteres) e pelo ano + NE + sequencial (12 ultimos). Referencia que casa
    -- com mais de uma NE nao herda nada.
    referencia_origem as (
        select distinct e.ne_ccor, m[1] as ug_origem, m[2] as sufixo_origem
        from empenhos as e
        cross join
            lateral regexp_match(
                e.ne_ccor_descricao, {{ regex_empenho_origem() }}, 'i'
            ) as m
        where m is not null
    ),

    empenho_origem as (
        select r.ne_ccor, min(o.ne_ccor) as ne_origem
        from referencia_origem as r
        inner join
            (select distinct ne_ccor from empenhos) as o
            on left(o.ne_ccor, 6) = r.ug_origem
            and right(o.ne_ccor, 12) = r.sufixo_origem
            and o.ne_ccor <> r.ne_ccor
        group by r.ne_ccor
        having count(distinct o.ne_ccor) = 1
    ),

    -- Primeiro exercicio em que cada NE foi inscrita em restos a pagar. As
    -- inscricoes dos exercicios seguintes sao reinscricoes: o saldo nao pago do
    -- mesmo dinheiro, que nao pode ser somado de novo.
    primeira_inscricao_rap as (
        select ne_ccor, min(right(emissao_dia, 4)::integer) as ano_primeira_inscricao
        from empenhos
        where emissao_dia ~ '^000/\d{4}$' and restos_a_pagar_inscritos <> 0
        group by ne_ccor
    )

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
    coalesce(
        e.emissao_dia ~ '^000/\d{4}$'
        and right(e.emissao_dia, 4)::integer > r.ano_primeira_inscricao,
        false
    ) as reinscricao_rap,
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

    -- Instrumento: TED tem precedencia; senao o convenio escolhido em
    -- vinculo_ne_convenio; senao o instrumento da NE de origem (NSSALDO), com a
    -- mesma precedencia. A heranca vai so um nivel.
    case
        when t.ne_ccor is not null
        then 'TED'
        when c.nr_convenio is not null
        then 'SICONV'
        when t_o.ne_ccor is not null
        then 'TED'
        when c_o.nr_convenio is not null
        then 'SICONV'
        else 'Não identificado'
    end as sistema_instrumento,
    case
        when t.ne_ccor is not null
        then t.id_plano_acao::text
        when c.nr_convenio is not null
        then c.nr_convenio
        when t_o.ne_ccor is not null
        then t_o.id_plano_acao::text
        when c_o.nr_convenio is not null
        then c_o.nr_convenio
    end as nr_instrumento,
    case
        when t.ne_ccor is not null
        then t.num_transf
        when c.nr_convenio is null and t_o.ne_ccor is not null
        then t_o.num_transf
    end as num_transf,
    case
        when t.ne_ccor is not null
        then 'ted: ' || t.metodo_ted
        when c.nr_convenio is not null and c.desempate_processo
        then 'convenio: ' || c.fonte_vinculo || ' (desempate por processo)'
        when c.nr_convenio is not null
        then 'convenio: ' || c.fonte_vinculo
        when t_o.ne_ccor is not null
        then 'empenho de origem: ted: ' || t_o.metodo_ted
        when c_o.nr_convenio is not null and c_o.desempate_processo
        then
            'empenho de origem: convenio: '
            || c_o.fonte_vinculo
            || ' (desempate por processo)'
        when c_o.nr_convenio is not null
        then 'empenho de origem: convenio: ' || c_o.fonte_vinculo
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
left join empenho_origem as eo on eo.ne_ccor = e.ne_ccor
left join ted as t_o on t_o.ne_ccor = eo.ne_origem
left join convenio as c_o on c_o.ne_ccor = eo.ne_origem
left join primeira_inscricao_rap as r on r.ne_ccor = e.ne_ccor
