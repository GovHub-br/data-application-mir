-- Avisa quando, num ano, o pago_total (pago no exercício + restos a pagar pagos depois) de
-- um instrumento passa o empenhado. Não se paga mais do que se empenhou, mas é aviso, não
-- erro: na NE em moeda estrangeira (a UG 364150 do CNPq paga em dólar), o empenhado vem do
-- relatório do PPA do ano de emissão e o RAP vem dos exercícios seguintes, e o Tesouro
-- reavalia o RAP pelo câmbio. Com um exercício carregado em "Moeda Origem" e o seguinte
-- em R$, o RAP em reais se soma a um empenhado em dólar (a moeda de origem é cobrada
-- nos testes de reconciliação com a consulta oficial,
-- test_execucao_ted_ne_reconcilia_oficial*); com todos em R$, sobra a variação do
-- câmbio. Fora disso, o estouro indica o mesmo pagamento de RAP contado mais de uma vez.
{{ config(severity="warn") }}

select
    ano,
    instrumento,
    empenhado,
    pago_total,
    pago_total - coalesce(empenhado, 0) as diferenca
from {{ ref("ted_execucao_por_instrumento") }}
where round(coalesce(pago_total, 0), 2) > round(coalesce(empenhado, 0), 2)
