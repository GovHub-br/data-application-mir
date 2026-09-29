{{ config(materialized="table") }}

-- Dotacao das emendas do MIR, uma linha por movimento do relatorio do Tesouro
-- (lancamentos positivos e negativos por dia; a soma e a dotacao do periodo).
-- Linhas identicas no mesmo dia sao movimentos distintos: a chave leva um
-- sequencial entre elas. O parlamentar e o autor com o partido vigente na data
-- do movimento (macro parlamentar_na_data, mesma regra das NEs).
with
    base as (
        select
            d.*,
            row_number() over (
                partition by
                    d.autor_emendas_orcamento,
                    d.emissao_dia,
                    d.programa_governo,
                    d.acao_governo,
                    d.ptres,
                    d.natureza_despesa,
                    d.modalidade_aplicacao,
                    d.fonte_recursos_detalhada,
                    d.localizador_gasto,
                    d.dotacao_inicial,
                    d.dotacao_atualizada
                order by d.dt_ingest
            ) as sequencial
        from {{ ref("tg_emendas_dotacao") }} as d
    ),

    movimentos as (
        select
            md5(
                concat_ws(
                    '|',
                    autor_emendas_orcamento,
                    emissao_dia,
                    programa_governo,
                    acao_governo,
                    ptres,
                    natureza_despesa,
                    modalidade_aplicacao,
                    fonte_recursos_detalhada,
                    localizador_gasto,
                    dotacao_inicial,
                    dotacao_atualizada,
                    sequencial
                )
            ) as id_movimento,
            base.*
        from base
    ),

    origem as (
        select
            id_movimento as chave,
            autor_emendas_orcamento_nome as autor_nome,
            emissao_dia as data_referencia
        from movimentos
    ),

    parlamentar as ({{ parlamentar_na_data("origem") }})

select
    m.id_movimento,
    m.autor_emendas_orcamento as codigo_emenda,
    m.autor_emendas_orcamento_descricao as emenda_descricao,
    m.autor_emendas_orcamento_nome as autor_nome,
    m.emissao_dia as data_movimento,
    lpad(m.programa_governo::text, 4, '0') as programa_governo,
    m.programa_governo_descricao,
    m.acao_governo,
    m.acao_governo_descricao,
    m.ptres::text as ptres,
    m.natureza_despesa,
    m.natureza_despesa_descricao,
    m.grupo_despesa,
    m.grupo_despesa_descricao,
    m.modalidade_aplicacao,
    m.fonte_recursos_detalhada,
    m.fonte_recursos_detalhada_descricao,
    m.localizador_gasto,
    m.localizador_gasto_descricao as localizador_descricao,
    m.regiao_pt as regiao,
    m.uf_pt as uf,
    m.uf_pt_descricao as uf_nome,
    m.dotacao_inicial,
    m.dotacao_atualizada,
    p.id_parlamentar,
    p.cargo_parlamentar,
    p.sigla_partido,
    p.prioridade_match
from movimentos as m
inner join parlamentar as p on p.chave = m.id_movimento
