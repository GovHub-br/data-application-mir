-- Falha se o residuo nao for exatamente o complemento do que entra no painel.
-- Issue #508: a decomposicao so e util se for exaustiva e sem sobreposicao.
--
-- A particao verificada e a mesma que a gold usa para somar empenhado
-- (valores_empenhados_tb): entra no painel a NE com num_transf nao nulo E que
-- nao canonicalize para vazio; todo o resto e residuo. Um num_transf de zeros
-- ('0', '000000') e nao nulo mas e descartado pela gold, por isso a
-- canonicalizacao entra na fronteira dos dois lados.
--
-- A verificacao e por IGUALDADE de contagem, nao por desigualdade: residuo e
-- subconjunto da fonte por construcao, entao um teste do tipo
-- `residuo > fonte` nunca poderia falhar e nao provaria cobertura. Somando os
-- dois lados e exigindo que batam com a fonte, uma linha que desaparecesse do
-- residuo seria pega mesmo se tivesse valor zero -- que a conferencia por
-- soma, isolada, deixaria passar.
--
-- A contagem do painel vem da propria cascata, nao de empenhos_por_plano_acao:
-- aquele modelo faz `select distinct` e pode colapsar linhas identicas, o que
-- tornaria a identidade de contagem invalida sem nenhum defeito real.

with fonte as (
    select
        count(*) as linhas,
        coalesce(sum(despesas_empenhadas), 0) as empenhado
    from {{ ref('ppa_tesouro') }}
    where ne_ccor <> '-9'
),

painel as (
    select
        count(*) as linhas,
        coalesce(sum(despesas_empenhadas), 0) as empenhado
    from {{ ref('empenhos_ted_cascata') }}
    where num_transf is not null
        and ltrim(trim(cast(num_transf as text)), '0') <> ''
),

residuo as (
    select
        count(*) as linhas,
        coalesce(sum(despesas_empenhadas), 0) as empenhado,
        count(*) filter (
            where num_transf is not null
                and ltrim(trim(cast(num_transf as text)), '0') <> ''
        ) as sobreposicao
    from {{ ref('empenhos_ted_residuo') }}
)

select
    fonte.linhas as linhas_fonte,
    painel.linhas as linhas_painel,
    residuo.linhas as linhas_residuo,
    fonte.empenhado as empenhado_fonte,
    painel.empenhado as empenhado_painel,
    residuo.empenhado as empenhado_residuo,
    residuo.sobreposicao as linhas_residuo_que_sao_painel
from fonte, painel, residuo
where residuo.sobreposicao <> 0
    or painel.linhas + residuo.linhas <> fonte.linhas
    or round(painel.empenhado + residuo.empenhado, 2)
        <> round(fonte.empenhado, 2)
