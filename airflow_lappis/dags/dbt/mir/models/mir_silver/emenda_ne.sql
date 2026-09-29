{{ config(materialized="table") }}

-- NEs de emenda, uma linha por NE: a emenda (tg_emendas), o localizador do
-- gasto e o parlamentar autor com o partido vigente na data de emissao da NE
-- (regra na macro parlamentar_na_data).
with
    nes as (
        select
            ne_ccor,
            max(codigo_emenda) as codigo_emenda,
            -- A emissao da NE e a primeira data que nao e inscricao de RAP; NE
            -- so com linhas de RAP usa a primeira inscricao
            coalesce(
                min(data_emissao) filter (where not inscricao_rap), min(data_emissao)
            ) as data_emissao_ne
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
        group by ne_ccor
    ),

    -- Cada NE tem um autor e um localizador no tg_emendas
    autores as (
        select distinct
            on (ne_ccor)
            ne_ccor,
            autor_emendas_orcamento_descricao as emenda_descricao,
            autor_emendas_orcamento_nome as autor_nome,
            localizador_gasto,
            localizador_gasto_descricao as localizador_descricao,
            regiao_pt as regiao,
            uf_pt as uf,
            uf_pt_descricao as uf_nome
        from {{ ref("tg_emendas") }}
        order by ne_ccor, autor_emendas_orcamento_descricao
    ),

    origem as (
        select n.ne_ccor as chave, a.autor_nome, n.data_emissao_ne as data_referencia
        from nes as n
        inner join autores as a on a.ne_ccor = n.ne_ccor
    ),

    parlamentar as ({{ parlamentar_na_data("origem") }})

select
    n.ne_ccor,
    n.codigo_emenda,
    a.emenda_descricao,
    a.autor_nome,
    n.data_emissao_ne,
    p.id_parlamentar,
    p.cargo_parlamentar,
    p.sigla_partido,
    p.prioridade_match,
    a.localizador_gasto,
    a.localizador_descricao,
    a.regiao,
    a.uf,
    a.uf_nome
from nes as n
inner join autores as a on a.ne_ccor = n.ne_ccor
inner join parlamentar as p on p.chave = n.ne_ccor
