-- Falha se alguma NE apontar para mais de um plano de acao na cascata de TED.
-- vinculo_ne_ted consolida por NE com max(); este teste garante que o max()
-- nao esconde conflito entre linhas da mesma NE.
select ne_ccor, count(distinct plano_acao) as qtd_planos
from {{ ref("empenhos_por_plano_acao") }}
where plano_acao is not null
group by ne_ccor
having count(distinct plano_acao) > 1

union all

-- E falha se o modelo perder ou duplicar NEs em relacao a cascata.
select 'contagem divergente' as ne_ccor, 0 as qtd_planos
where
    (select count(*) from {{ ref("vinculo_ne_ted") }}) <> (
        select count(distinct ne_ccor)
        from {{ ref("empenhos_por_plano_acao") }}
        where plano_acao is not null
    )
