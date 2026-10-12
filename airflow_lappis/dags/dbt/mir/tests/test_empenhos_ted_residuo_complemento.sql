-- Falha se o residuo nao for exatamente o complemento do que entra no painel.
-- Issue #508: a decomposicao so e util se for exaustiva e sem sobreposicao.
-- A cascata e ephemeral, entao nao da para consulta-la direto; o teste usa a
-- identidade que a torna verificavel a partir dos modelos materializados:
--   residuo (num_transf nulo) + empenhos_por_plano_acao com num_transf
--   = toda NE de ppa_tesouro (fora as linhas de dotacao)
-- Isso cobre as duas promessas de uma vez: a cascata nao perde nem duplica
-- linha, e o residuo cobre todo o descarte. Se um refactor quebrar qualquer uma
-- das duas, a contagem ou a soma divergem aqui.
-- empenhos_por_plano_acao faz `select distinct`, entao a contagem dele pode
-- colapsar linhas identicas; por isso a verificacao de linha usa a fonte e o
-- residuo, e o valor e conferido pelos tres.

with fonte as (
    select
        count(*) as linhas,
        coalesce(sum(despesas_empenhadas), 0) as empenhado
    from {{ ref('ppa_tesouro') }}
    where ne_ccor <> '-9'
),

residuo as (
    select
        count(*) as linhas,
        coalesce(sum(despesas_empenhadas), 0) as empenhado,
        count(*) filter (where num_transf is not null) as invalidas
    from {{ ref('empenhos_ted_residuo') }}
),

vinculado as (
    select
        coalesce(sum(despesas_empenhadas), 0) as empenhado
    from {{ ref('empenhos_por_plano_acao') }}
    where num_transf is not null
)

select
    fonte.linhas as linhas_fonte,
    residuo.linhas as linhas_residuo,
    fonte.empenhado as empenhado_fonte,
    residuo.empenhado as empenhado_residuo,
    vinculado.empenhado as empenhado_vinculado,
    residuo.invalidas as residuo_com_num_transf
from fonte, residuo, vinculado
where residuo.invalidas <> 0
    or residuo.linhas > fonte.linhas
    or round(residuo.empenhado + vinculado.empenhado, 2)
        <> round(fonte.empenhado, 2)
