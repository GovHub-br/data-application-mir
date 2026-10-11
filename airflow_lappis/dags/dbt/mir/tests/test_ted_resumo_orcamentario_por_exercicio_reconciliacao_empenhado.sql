-- Falha se o total de empenhado aberto por exercicio divergir do total de TED
-- em ted_resumo_orcamentario — a quebra por ano (ne_ccor_ano_emissao) nao pode
-- perder nem duplicar valor em relacao ao agregado por instrumento.

with por_exercicio as (
    select coalesce(sum(empenhado), 0) as total
    from {{ ref('ted_resumo_orcamentario_por_exercicio') }}
),

resumo as (
    select coalesce(sum(empenhado), 0) as total
    from {{ ref('ted_resumo_orcamentario') }}
    where tipo_instrumento = 'TED'
)

select
    por_exercicio.total as total_por_exercicio,
    resumo.total as total_resumo
from por_exercicio, resumo
where round(por_exercicio.total, 2) <> round(resumo.total, 2)
