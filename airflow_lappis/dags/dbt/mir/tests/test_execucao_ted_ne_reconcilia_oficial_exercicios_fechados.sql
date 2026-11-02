-- Falha quando, num exercício fechado (a partir de 1º de março do ano seguinte; ver a
-- macro ted_execucao_divergencia_oficial), as NEs não reproduzem, célula a célula, a
-- consulta oficial "Execução TED por UG" (empenhado, liquidado e pago). Com o ano
-- encerrado, os dois relatórios do Tesouro Gerencial são definitivos e têm de bater ao
-- centavo. Causa conhecida: o relatório de NEs
-- (email_tesouro_ppa_ingest_dag) carregado com a métrica "Moeda Origem" em vez de "R$".
-- A UG 364150 do CNPq empenha em dólar, e o valor em dólar chega como se fosse real. A
-- correção é reenviar o relatório do exercício com a métrica em R$, não converter no dbt:
-- o Tesouro reavalia essas NEs pelo câmbio. Os exercícios ainda não fechados ficam no
-- aviso test_execucao_ted_ne_reconcilia_oficial.
--
-- Exceção temporária: a UG 364150 em 2023-2025 ainda está em "Moeda Origem" e fica no
-- aviso test_execucao_ted_ne_reconcilia_oficial_cnpq_moeda_origem. Quando esse aviso
-- devolver 0 linhas, depois de reextrair o relatório desses anos em R$, o filtro abaixo
-- e o aviso saem juntos. "is distinct from" para uma célula com UG nula continuar
-- reprovando.
select divergencia.*
from ({{ ted_execucao_divergencia_oficial("fechados") }}) as divergencia
where
    divergencia.ug is distinct from '364150' or divergencia.ano not between 2023 and 2025
