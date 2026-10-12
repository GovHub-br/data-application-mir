-- Falha se o relatorio de auditoria nao fechar com a fonte da cascata.
-- Issue #508, critério de aceite: o relatorio tem que ser uma contabilidade
-- completa de para onde vai cada real, entao suas somas precisam reproduzir as
-- de ppa_tesouro. Se um grupo do relatorio perder linhas (ex.: um join que
-- virou inner, ou uma categoria nova que caiu fora dos eixos de agrupamento),
-- a diferenca aparece aqui em vez de passar como um numero plausivel.
-- A cascata e ephemeral, logo a referencia e ppa_tesouro, que e a sua fonte e
-- da qual ela preserva linha a linha.

with relatorio as (
    select
        coalesce(sum(qtd_nes), 0) as linhas,
        coalesce(sum(empenhado), 0) as empenhado,
        coalesce(sum(liquidado), 0) as liquidado
    from {{ ref('ted_auditoria_cascata') }}
),

fonte as (
    select
        count(*) as linhas,
        coalesce(
            sum(case when despesas_empenhadas > 0 then despesas_empenhadas else 0 end), 0
        ) as empenhado,
        coalesce(sum(despesas_liquidadas), 0) as liquidado
    from {{ ref('ppa_tesouro') }}
    where ne_ccor <> '-9'
)

select
    relatorio.linhas as linhas_relatorio,
    fonte.linhas as linhas_fonte,
    relatorio.empenhado as empenhado_relatorio,
    fonte.empenhado as empenhado_fonte,
    relatorio.liquidado as liquidado_relatorio,
    fonte.liquidado as liquidado_fonte
from relatorio, fonte
where relatorio.linhas <> fonte.linhas
    or round(relatorio.empenhado, 2) <> round(fonte.empenhado, 2)
    or round(relatorio.liquidado, 2) <> round(fonte.liquidado, 2)
