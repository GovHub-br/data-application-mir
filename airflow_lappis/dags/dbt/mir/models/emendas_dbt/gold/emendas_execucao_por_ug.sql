{{ config(materialized="table") }}

-- Execucao (empenhado/liquidado/pago) das emendas parlamentares detalhada por
-- Unidade Gestora executora. Complementa resumo_emendas_orcamento_execucao
-- (que e por parlamentar): aqui a mesma execucao aparece quebrada por UG, para
-- responder "quanto cada UG executou das emendas do autor".
--
-- NAO traz dotacao de proposito: a dotacao e definida no grao da classificacao
-- orcamentaria (sem UG) e, se repetida por UG, somaria em dobro — para
-- orcamento (dotado x executado) use resumo_emendas_orcamento_execucao.
--
-- Grao: autor_emendas_orcamento_nome x UG executora. Linhas com UG nula sao a
-- execucao ainda nao atribuida a uma UG (empenho sem ne_ccor correspondente).

with
    base as (select * from {{ ref("emendas_partidos") }})

select

    autor_emendas_orcamento_nome,
    ug_responsavel_codigo,
    ug_responsavel_nome,
    max(id_autor) as id_autor,
    max(autor) as autor,
    max(cargo_autor) as cargo_autor,
    max(partido) as partido,
    max(uf_autor) as uf_autor,
    max(url_foto_autor) as url_foto_autor,
    max(url_foto_partido) as url_foto_partido,

    count(*) as quantidade_empenhos,
    count(distinct localizador_gasto) as quantidade_localizadores,

    -- Execucao (por UG)
    sum(despesas_empenhadas) as despesas_empenhadas,
    sum(despesas_liquidadas) as despesas_liquidadas,
    sum(despesas_pagas) as despesas_pagas,
    sum(restos_a_pagar_inscritos) as restos_a_pagar_inscritos,
    sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,

    max(dt_ingest) as dt_ingest

from base
group by
    autor_emendas_orcamento_nome,
    ug_responsavel_codigo,
    ug_responsavel_nome
