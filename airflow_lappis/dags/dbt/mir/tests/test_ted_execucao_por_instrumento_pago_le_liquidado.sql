-- Falha se, num ano, o pago de um instrumento passar o liquidado (issue #509, epico
-- #506). Liquidado e pago aqui sao os do exercicio, sem RAP, como na consulta
-- oficial "Execucao TED por UG" e no levantamento da CGPO: e preciso liquidar para
-- pagar, entao pago <= liquidado. Diferente de ted_resumo_orcamentario, cada NE vai
-- inteira para um unico instrumento (ou para '(não identificado)'), entao a regra
-- vale sem excecao.
select ano, instrumento, liquidado, pago, pago - coalesce(liquidado, 0) as diferenca
from {{ ref("ted_execucao_por_instrumento") }}
where round(coalesce(pago, 0), 2) > round(coalesce(liquidado, 0), 2)
