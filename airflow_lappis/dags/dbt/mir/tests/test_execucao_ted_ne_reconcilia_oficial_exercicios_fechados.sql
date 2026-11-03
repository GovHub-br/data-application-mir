-- Falha quando, num exercício fechado (a partir de 1º de março do ano seguinte; ver a
-- macro ted_execucao_divergencia_oficial), as NEs não reproduzem, célula a célula, a
-- consulta oficial "Execução TED por UG" (empenhado, liquidado e pago). Com o ano
-- encerrado, os dois relatórios do Tesouro Gerencial são definitivos e têm de bater ao
-- centavo. Causa conhecida: o relatório de NEs (email_tesouro_ppa_ingest_dag) carregado
-- com a métrica "Moeda Origem" em vez de "R$". Os exercícios ainda não fechados ficam no
-- aviso test_execucao_ted_ne_reconcilia_oficial.
--
-- A UG 364150 do CNPq empenha em dólar. Enquanto 2023-2025 não forem reextraídos em R$,
-- ppa_tesouro converte essas NEs pela taxa do seed cambio_fechamento_exercicio, e este
-- teste vigia a conversão: falha se o relatório reextraído em R$ chegar com o seed
-- ainda ativo (valor multiplicado de novo), ou se faltar a taxa de um ano.
select divergencia.*
from ({{ ted_execucao_divergencia_oficial("fechados") }}) as divergencia
