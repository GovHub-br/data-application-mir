-- Avisa das células que test_execucao_ted_ne_reconcilia_oficial_exercicios_fechados deixa
-- de fora: a UG 364150 do CNPq, que empenha em dólar, em 2023-2025, exercícios cujo
-- relatório de NEs foi carregado com a métrica "Moeda Origem". A correção é reextrair
-- esses anos em R$ no Tesouro Gerencial. Quando este teste devolver 0 linhas, ele e o
-- filtro daquele teste saem juntos. Linha além das três células conhecidas (uma por
-- ano) precisa ser investigada: aqui ela só avisa.
{{ config(severity="warn") }}

select divergencia.*
from ({{ ted_execucao_divergencia_oficial("fechados") }}) as divergencia
where divergencia.ug = '364150' and divergencia.ano between 2023 and 2025
