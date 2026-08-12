{{ config(materialized="table") }}

-- Resumo por parlamentar do orcamento (dotado) x execucao das emendas.
-- Cada linha da silver e uma classificacao orcamentaria (linha de emenda);
-- aqui somamos por autor. Como dotacao e execucao ja chegam no mesmo grao,
-- as somas nao tem dupla contagem.
--
-- Agrupamos por autor_emendas_orcamento_nome (sempre presente) para nao
-- perder autores sem correspondencia na base de parlamentares; os atributos
-- do parlamentar sao carregados via max() (nulos quando nao houve match).

with
    base as (select * from {{ ref("emendas_orcamento_execucao") }})

select
    autor_emendas_orcamento_nome,
    max(id_autor) as id_autor,
    max(autor) as autor,
    max(cargo_autor) as cargo_autor,
    max(partido) as partido,
    max(uf_autor) as uf_autor,
    max(url_foto_autor) as url_foto_autor,
    max(url_foto_partido) as url_foto_partido,

    count(*) as quantidade_linhas_orcamentarias,
    count(distinct localizador_gasto) as quantidade_localizadores,

    -- Orcamento
    sum(dotacao_inicial) as dotacao_inicial,
    sum(dotacao_atualizada) as dotacao_atualizada,

    -- Execucao
    sum(despesas_empenhadas) as despesas_empenhadas,
    sum(despesas_liquidadas) as despesas_liquidadas,
    sum(despesas_pagas) as despesas_pagas,
    sum(restos_a_pagar_inscritos) as restos_a_pagar_inscritos,
    sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,

    -- Indicadores
    (sum(dotacao_atualizada) - sum(despesas_empenhadas))::numeric(15, 2)
        as saldo_a_empenhar,
    round(
        sum(despesas_empenhadas) / nullif(sum(dotacao_atualizada), 0), 4
    ) as percentual_empenhado,
    round(
        sum(despesas_pagas) / nullif(sum(dotacao_atualizada), 0), 4
    ) as percentual_pago,

    max(dt_ingest) as dt_ingest

from base
group by autor_emendas_orcamento_nome
