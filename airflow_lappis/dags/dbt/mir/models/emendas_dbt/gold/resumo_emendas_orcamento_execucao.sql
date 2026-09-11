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
    base as (select * from {{ ref("emendas_orcamento_execucao") }}),

    -- UGs executoras por parlamentar, consolidadas (string_agg) a partir do
    -- grao de execucao (emendas_partidos). Aqui a UG e atributo do resumo; o
    -- detalhe de quanto cada UG executou vive em emendas_execucao_por_ug.
    ugs_por_autor as (
        select
            autor_emendas_orcamento_nome,
            string_agg(
                distinct cast(ug_responsavel_codigo as text),
                ', '
                order by cast(ug_responsavel_codigo as text)
            ) as ug_responsavel_codigo,
            string_agg(
                distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome
            ) as ug_responsavel_nome,
            count(distinct ug_responsavel_codigo) as qtd_ugs_responsaveis
        from {{ ref("emendas_partidos") }}
        where ug_responsavel_codigo is not null
        group by autor_emendas_orcamento_nome
    )

select

    autor_emendas_orcamento_nome,
    u.ug_responsavel_codigo,
    u.ug_responsavel_nome,
    coalesce(u.qtd_ugs_responsaveis, 0) as qtd_ugs_responsaveis,
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
left join ugs_por_autor u using (autor_emendas_orcamento_nome)
group by
    autor_emendas_orcamento_nome,
    u.ug_responsavel_codigo,
    u.ug_responsavel_nome,
    u.qtd_ugs_responsaveis