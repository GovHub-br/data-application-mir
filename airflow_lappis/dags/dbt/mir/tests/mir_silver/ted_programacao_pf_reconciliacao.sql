-- Falha se ted_programacao_pf perder ou duplicar linhas ou valor da PF do
-- Tesouro.
select
    (select count(*) from {{ ref("ted_programacao_pf") }}) as linhas_silver,
    (select count(*) from {{ ref("pf_tesouro") }}) as linhas_bronze,
    (select sum(valor) from {{ ref("ted_programacao_pf") }}) as valor_silver,
    (select sum(pf_valor_linha) from {{ ref("pf_tesouro") }}) as valor_bronze
where
    (select count(*) from {{ ref("ted_programacao_pf") }})
    <> (select count(*) from {{ ref("pf_tesouro") }})
    or (select sum(valor) from {{ ref("ted_programacao_pf") }})
    <> (select sum(pf_valor_linha) from {{ ref("pf_tesouro") }})
