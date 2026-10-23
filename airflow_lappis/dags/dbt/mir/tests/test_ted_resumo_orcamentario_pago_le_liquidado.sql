-- Falha se, para uma mesma transferencia, o pago do exercicio passar o liquidado
-- do exercicio (hipotese 3, pag. 7 da devolutiva, epico #506). E preciso
-- liquidar para pagar, entao no mesmo escopo pago <= liquidado. O par comparado
-- e o do exercicio corrente: pago + RAP contra liquidado mistura escopos (o RAP
-- pago foi liquidado em exercicio anterior ou e RAP liquidado, que a fonte nao
-- traz) e por isso nao e testado aqui.
--
-- No grao da NE a regra vale em toda a fonte; quando quebra no grao da
-- transferencia, e porque a cascata atribuiu ao TED so parte das linhas de uma
-- NE (ex.: o pagamento cita o TED no doc_observacao e a liquidacao nao). Cada
-- excecao conhecida entra na lista abaixo com a justificativa; uma violacao nova
-- faz o teste falhar ate ser corrigida ou explicada aqui.
{% set excecoes = {
    "973280": "NE 154040152572026NE000204 (energia eletrica da UG executora): "
    ~ "dois pagamentos citam o TED 973280/2026PF000062 no doc_observacao, "
    ~ "a liquidacao correspondente nao cita",
} %}

select
    num_transf,
    liquidado_exercicio,
    pago_exercicio,
    pago_exercicio - coalesce(liquidado_exercicio, 0) as diferenca
from {{ ref("ted_resumo_orcamentario") }}
where
    tipo_instrumento = 'TED'
    and pago_excede_liquidado
    and num_transf not in ('{{ excecoes.keys() | join("', '") }}')
