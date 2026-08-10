{{ config(materialized="table") }}

-- Junta orcamento (dotado) e execucao (empenhado/liquidado/pago) das emendas
-- parlamentares no MESMO grao: a classificacao orcamentaria
--   (programa, acao, localizador, natureza, modalidade, fonte, ptres).
--
-- Regra de negocio:
--   - A dotacao (itens 9/13) e definida no grao da classificacao, sem empenho.
--     Uma classificacao mapeia para exatamente um autor de emenda.
--   - Varios empenhos executam contra a mesma classificacao. Por isso a
--     execucao e AGREGADA a esse grao antes de juntar — evita repetir a
--     dotacao por empenho (dupla contagem ao somar).
--   - A base e a dotacao (LEFT JOIN execucao): linhas dotadas mas ainda nao
--     empenhadas aparecem com execucao = 0. O caminho inverso perderia essas
--     linhas.

with
    dotacao as (
        select
            programa_governo,
            acao_governo,
            localizador_gasto,
            natureza_despesa,
            modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres,
            -- Atributos funcao da classificacao (1:1) — max() e so para
            -- reduzir ao grao sem precisar agrupar por texto.
            max(programa_governo_descricao) as programa_governo_descricao,
            max(acao_governo_descricao) as acao_governo_descricao,
            max(autor_emendas_orcamento) as autor_emendas_orcamento,
            max(autor_emendas_orcamento_descricao) as autor_emendas_orcamento_descricao,
            max(autor_emendas_orcamento_nome) as autor_emendas_orcamento_nome,
            max(localizador_gasto_descricao) as localizador_gasto_descricao,
            max(regiao_pt) as regiao_pt,
            max(uf_pt) as uf_pt,
            max(uf_pt_descricao) as uf_pt_descricao,
            max(municipio_pt) as municipio_pt,
            max(grupo_despesa) as grupo_despesa,
            max(grupo_despesa_descricao) as grupo_despesa_descricao,
            max(natureza_despesa_descricao) as natureza_despesa_descricao,
            max(modalidade_aplicacao_descricao) as modalidade_aplicacao_descricao,
            max(fonte_recursos_detalhada_descricao) as fonte_recursos_detalhada_descricao,
            sum(dotacao_inicial) as dotacao_inicial,
            sum(dotacao_atualizada) as dotacao_atualizada,
            max(dt_ingest) as dt_ingest
        from {{ ref("tg_emendas_dotacao") }}
        group by
            programa_governo,
            acao_governo,
            localizador_gasto,
            natureza_despesa,
            modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres
    ),

    execucao as (
        select
            programa_governo,
            acao_governo,
            localizador_gasto,
            natureza_despesa,
            modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres,
            sum(despesas_empenhadas) as despesas_empenhadas,
            sum(despesas_liquidadas) as despesas_liquidadas,
            sum(despesas_pagas) as despesas_pagas,
            sum(restos_a_pagar_inscritos) as restos_a_pagar_inscritos,
            sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,
            max(dt_ingest) as dt_ingest
        from {{ ref("tg_emendas") }}
        group by
            programa_governo,
            acao_governo,
            localizador_gasto,
            natureza_despesa,
            modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres
    ),

    -- Um registro por parlamentar (filiacao mais recente), para atribuir a
    -- emenda ao autor via nome. Como o modelo e agregado no ano, nao ha data
    -- de emissao para priorizar por vigencia — usamos a filiacao mais recente.
    parlamentar as (
        select distinct on (chave_join_nome)
            chave_join_nome,
            id_parlamentar,
            cargo_parlamentar,
            nome_parlamentar,
            sigla_partido,
            uf_parlamentar,
            url_foto,
            email,
            url_logo_partido
        from {{ ref("parlamentares_historico") }}
        order by chave_join_nome, data_filiacao desc nulls last
    )

select
    -- Classificacao orcamentaria (grao)
    d.programa_governo as codigo_programa,
    d.programa_governo_descricao as programa,
    d.acao_governo as codigo_acao,
    d.acao_governo_descricao as acao,
    d.localizador_gasto,
    d.localizador_gasto_descricao,
    d.regiao_pt,
    d.uf_pt as uf,
    d.uf_pt_descricao as uf_descricao,
    d.municipio_pt as municipio,
    d.grupo_despesa as codigo_gnd,
    d.grupo_despesa_descricao as gnd,
    d.natureza_despesa,
    d.natureza_despesa_descricao,
    d.modalidade_aplicacao as codigo_modalidade,
    d.modalidade_aplicacao_descricao as modalidade,
    d.ptres,
    d.fonte_recursos_detalhada,
    d.fonte_recursos_detalhada_descricao,

    -- Autor da emenda
    d.autor_emendas_orcamento,
    d.autor_emendas_orcamento_descricao,
    d.autor_emendas_orcamento_nome,

    -- Orcamento (dotado)
    d.dotacao_inicial,
    d.dotacao_atualizada,

    -- Execucao (0 quando dotado mas ainda nao empenhado)
    coalesce(e.despesas_empenhadas, 0)::numeric(15, 2) as despesas_empenhadas,
    coalesce(e.despesas_liquidadas, 0)::numeric(15, 2) as despesas_liquidadas,
    coalesce(e.despesas_pagas, 0)::numeric(15, 2) as despesas_pagas,
    coalesce(e.restos_a_pagar_inscritos, 0)::numeric(15, 2) as restos_a_pagar_inscritos,
    coalesce(e.restos_a_pagar_pagos, 0)::numeric(15, 2) as restos_a_pagar_pagos,

    -- Indicadores orcamento x execucao
    (d.dotacao_atualizada - coalesce(e.despesas_empenhadas, 0))::numeric(15, 2)
        as saldo_a_empenhar,
    round(
        coalesce(e.despesas_empenhadas, 0) / nullif(d.dotacao_atualizada, 0), 4
    ) as percentual_empenhado,
    round(
        coalesce(e.despesas_pagas, 0) / nullif(d.dotacao_atualizada, 0), 4
    ) as percentual_pago,

    -- Parlamentar
    p.id_parlamentar as id_autor,
    p.cargo_parlamentar as cargo_autor,
    p.nome_parlamentar as autor,
    p.sigla_partido as partido,
    p.uf_parlamentar as uf_autor,
    p.url_foto as url_foto_autor,
    p.email as email_autor,
    p.url_logo_partido as url_foto_partido,

    greatest(d.dt_ingest, coalesce(e.dt_ingest, d.dt_ingest)) as dt_ingest

from dotacao d
left join execucao e
    on d.programa_governo = e.programa_governo
    and d.acao_governo = e.acao_governo
    and d.localizador_gasto = e.localizador_gasto
    and d.natureza_despesa = e.natureza_despesa
    and d.modalidade_aplicacao = e.modalidade_aplicacao
    and d.fonte_recursos_detalhada = e.fonte_recursos_detalhada
    and d.ptres = e.ptres
left join parlamentar p
    on {{ name_formater("d.autor_emendas_orcamento_nome") }} = p.chave_join_nome
