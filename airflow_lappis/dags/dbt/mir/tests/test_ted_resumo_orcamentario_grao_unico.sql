-- Falha se o grao (tipo_instrumento, num_transf/processo) nao for unico em
-- ted_resumo_orcamentario. Protege contra fan-out (ex.: join com emendas ou
-- com a ponte de plano_acao voltar a multiplicar linhas) e contra quebra do
-- grao. Atualizado para o grao de instrumento (issue #507): TED e chaveado
-- por num_transf, tedinho por processo -- coalesce(num_transf, processo) com
-- tipo_instrumento cobre os dois. Corrige o teste original, que referenciava
-- ug_responsavel_codigo/ug_responsavel_nome -- colunas removidas no
-- refactor que consolidou as UGs em ugs_responsaveis_codigos/nomes.

select
    tipo_instrumento,
    coalesce(num_transf, processo) as identificador,
    count(*) as n_linhas
from {{ ref('ted_resumo_orcamentario') }}
group by tipo_instrumento, coalesce(num_transf, processo)
having count(*) > 1
