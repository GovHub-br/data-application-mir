-- Falha se, num ano, o pago_total (pago no exercicio + restos a pagar pagos depois) de um
-- instrumento passar o empenhado. Nao se paga mais do que se empenhou; se passar, o
-- relatorio do PPA trouxe o mesmo pagamento de RAP mais de uma vez.
select
    ano,
    instrumento,
    empenhado,
    pago_total,
    pago_total - coalesce(empenhado, 0) as diferenca
from {{ ref("ted_execucao_por_instrumento") }}
where round(coalesce(pago_total, 0), 2) > round(coalesce(empenhado, 0), 2)
