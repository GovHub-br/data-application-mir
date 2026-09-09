-- Falha se o total de empenhado no resumo divergir da fonte
-- (empenhos_por_plano_acao, transferencias com num_transf nao nulo). Empenho e o
-- unico bloco no grao de ug, entao seu total deve ser preservado 1:1 — este teste
-- pega qualquer dupla contagem ou perda causada por fan-out no join de consolidacao.

with gold as (
    select coalesce(sum(empenhado), 0) as total
    from {{ ref('ted_resumo_orcamentario') }}
),

fonte as (
    select coalesce(
        sum(case when despesas_empenhadas > 0 then despesas_empenhadas else 0 end), 0
    ) as total
    from {{ ref('empenhos_por_plano_acao') }}
    where num_transf is not null
        and ltrim(trim(cast(num_transf as text)), '0') <> ''
)

select
    gold.total as total_gold,
    fonte.total as total_fonte
from gold, fonte
where round(gold.total, 2) <> round(fonte.total, 2)
