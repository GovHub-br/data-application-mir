-- Uma linha por célula da consulta oficial (ano x UG x ação x PO x PTRES x grupo x
-- fonte): a DAG substitui o ano inteiro a cada anexo, então repetição indica
-- carga duplicada ou mudança no layout do relatório.
select
    ano_lancamento,
    ug_executora_codigo,
    acao_governo_codigo,
    plano_orcamentario_codigo,
    ptres,
    grupo_despesa,
    fonte_recursos_detalhada,
    count(*) as linhas
from {{ ref("execucao_ted_ug") }}
group by 1, 2, 3, 4, 5, 6, 7
having count(*) > 1
