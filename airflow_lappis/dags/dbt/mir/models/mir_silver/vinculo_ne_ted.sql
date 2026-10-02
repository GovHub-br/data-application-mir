{{ config(materialized="table") }}

-- Vinculo NE -> plano de acao de TED, no grao da NE. Le a cascata de extracao
-- de num_transf (ted_ne_transferencia, validada metodo a metodo) e resolve o
-- plano pela ponte ted_plano_instrumento (sq_instrumento do TransfereGov, que e
-- o num_transf do SIAFI). Cada NE tem no maximo um plano (garantido pelo teste
-- vinculo_ne_ted_plano_unico), entao max() nao escolhe entre valores.
with
    linhas as (
        select t.ne_ccor, t.num_transf, t.metodo, p.id_plano_acao
        from {{ ref("ted_ne_transferencia") }} as t
        inner join {{ ref("ted_plano_instrumento") }} as p on p.num_transf = t.num_transf
    )

select
    ne_ccor,
    max(id_plano_acao) as id_plano_acao,
    max(num_transf) as num_transf,
    string_agg(distinct metodo, ', ' order by metodo) as metodo_ted
from linhas
group by ne_ccor
