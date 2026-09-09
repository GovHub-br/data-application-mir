-- Falha se a ponte num_transf_n_plano_acao mapear uma mesma transferencia (canonica)
-- para mais de um plano_acao. ted_resumo_orcamentario assume essa relacao 1:1 ao
-- resolver plano_acao como atributo da transferencia; se deixar de valer, o join da
-- ponte reintroduziria fan-out.

select
    ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
    count(distinct plano_acao) as n_planos
from {{ ref('num_transf_n_plano_acao') }}
where num_transf is not null
    and ltrim(trim(cast(num_transf as text)), '0') <> ''
group by ltrim(trim(cast(num_transf as text)), '0')
having count(distinct plano_acao) > 1
