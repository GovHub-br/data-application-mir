{{ config(materialized="table") }}

-- Vinculo NE -> plano de acao de TED, no grao da NE.
-- Reaproveita a cascata de extracao de num_transf de empenhos_por_plano_acao
-- (validada metodo a metodo); aqui apenas consolidamos as linhas por NE.
-- Cada NE tem no maximo um plano (garantido pelo teste
-- vinculo_ne_ted_plano_unico), entao max() nao escolhe entre valores.
select
    ne_ccor,
    max(plano_acao) as id_plano_acao,
    max(num_transf) as num_transf,
    string_agg(distinct metodo, ', ' order by metodo) as metodo_ted
from {{ ref("empenhos_por_plano_acao") }}
where plano_acao is not null
group by ne_ccor
