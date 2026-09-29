{{ config(severity="warn") }}

-- Aviso (nao bloqueia a DAG): a reinscricao de restos a pagar e o saldo do
-- mesmo dinheiro, entao nunca pode passar da inscricao anterior da NE menos os
-- restos a pagar pagos naquele exercicio. Valor maior indica reforco ou dado
-- inconsistente, e a regra de contar so a primeira inscricao deixaria de valer.
-- Linha de base em 2026-09-29: 0 (164 reinscricoes, todas iguais ao saldo ou
-- menores por cancelamento).
with
    inscricoes as (
        select
            ne_ccor,
            extract(year from data_emissao)::integer as ano,
            sum(restos_a_pagar_inscritos) as inscrito
        from {{ ref("execucao_ne") }}
        where inscricao_rap
        group by ne_ccor, extract(year from data_emissao)
        having sum(restos_a_pagar_inscritos) <> 0
    ),

    pagamentos as (
        select
            ne_ccor,
            extract(year from data_emissao)::integer as ano,
            sum(restos_a_pagar_pagos) as rap_pago
        from {{ ref("execucao_ne") }}
        where not inscricao_rap
        group by ne_ccor, extract(year from data_emissao)
    ),

    sequencia as (
        select
            ne_ccor,
            ano,
            inscrito,
            lag(ano) over (partition by ne_ccor order by ano) as ano_anterior,
            lag(inscrito) over (partition by ne_ccor order by ano) as inscrito_anterior
        from inscricoes
    )

select s.ne_ccor, s.ano, s.inscrito, s.inscrito_anterior, p.rap_pago
from sequencia as s
left join pagamentos as p on p.ne_ccor = s.ne_ccor and p.ano = s.ano_anterior
where
    s.ano_anterior is not null
    and s.inscrito > s.inscrito_anterior - coalesce(p.rap_pago, 0) + 0.01
