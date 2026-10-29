-- Avisa quando, num exercício ainda não fechado (o ano de hoje e, em janeiro e fevereiro,
-- também o anterior), as NEs não reproduzem, célula a célula, a consulta oficial
-- "Execução TED por UG" (empenhado, liquidado e pago). A atribuição por instrumento só
-- fecha com o oficial se a base de NEs fechar. É aviso, não erro: as duas consultas podem
-- ser extraídas em dias diferentes (ver a var ted_execucao_corte_emissao em
-- execucao_ted_ne). Nos exercícios fechados a diferença é erro
-- (test_execucao_ted_ne_reconcilia_oficial_exercicios_fechados).
{{ config(severity="warn") }}

{{ ted_execucao_divergencia_oficial("corrente") }}
