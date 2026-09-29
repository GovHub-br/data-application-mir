-- Falha se algum PTRES do nucleo aparecer com mais de um programa, acao ou
-- plano orcamentario: dim_acao_orcamentaria guarda um conjunto de atributos
-- por PTRES e rotularia errado as linhas do outro conjunto.
select
    ptres,
    count(distinct programa_governo) as qtd_programas,
    count(distinct acao_governo) as qtd_acoes,
    count(distinct plano_orcamentario_codigo_po) as qtd_planos
from {{ ref("execucao_ne") }}
group by ptres
having
    count(distinct programa_governo) > 1
    or count(distinct acao_governo) > 1
    or count(distinct plano_orcamentario_codigo_po) > 1
