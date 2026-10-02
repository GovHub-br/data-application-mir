-- Falha se emenda_dotacao perder ou duplicar movimentos ou valor da dotacao do
-- Tesouro.
with
    silver as (
        select
            count(*) as linhas,
            sum(dotacao_inicial) as inicial,
            sum(dotacao_atualizada) as atualizada
        from {{ ref("emenda_dotacao") }}
    ),

    bronze as (
        select
            count(*) as linhas,
            sum(dotacao_inicial) as inicial,
            sum(dotacao_atualizada) as atualizada
        from {{ ref("tg_emendas_dotacao") }}
    )

select s.*, b.linhas as linhas_bronze
from silver as s
cross join bronze as b
where s.linhas <> b.linhas or s.inicial <> b.inicial or s.atualizada <> b.atualizada
