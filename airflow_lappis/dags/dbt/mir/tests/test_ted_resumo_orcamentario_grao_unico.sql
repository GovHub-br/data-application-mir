-- Falha se o grao (num_transf, ug_responsavel_codigo, ug_responsavel_nome) nao for
-- unico em ted_resumo_orcamentario. Protege contra fan-out (ex.: join com emendas ou
-- com a ponte de plano_acao voltar a multiplicar linhas) e contra quebra do grao.

select
    num_transf,
    ug_responsavel_codigo,
    ug_responsavel_nome,
    count(*) as n_linhas
from {{ ref('ted_resumo_orcamentario') }}
group by num_transf, ug_responsavel_codigo, ug_responsavel_nome
having count(*) > 1
