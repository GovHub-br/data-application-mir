-- Falha se as fatos de Emendas perderem ou duplicarem linhas ou valores em
-- relacao a silver. Cada medida e comparada sozinha, para um erro nao
-- compensar outro.
with
    execucao_fato as (
        select
            count(*) as linhas,
            coalesce(sum(despesas_empenhadas), 0) as empenhado,
            coalesce(sum(despesas_liquidadas), 0) as liquidado,
            coalesce(sum(despesas_pagas), 0) as pago,
            coalesce(sum(restos_a_pagar_inscritos), 0) as rap_inscrito,
            coalesce(sum(restos_a_pagar_pagos), 0) as rap_pago
        from {{ ref("emendas_fato_execucao_orcamentaria") }}
    ),

    execucao_silver as (
        select
            count(*) as linhas,
            coalesce(sum(despesas_empenhadas), 0) as empenhado,
            coalesce(sum(despesas_liquidadas), 0) as liquidado,
            coalesce(sum(despesas_pagas), 0) as pago,
            coalesce(sum(restos_a_pagar_inscritos), 0) as rap_inscrito,
            coalesce(sum(restos_a_pagar_pagos), 0) as rap_pago
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
    ),

    dotacao_fato as (
        select
            count(*) as linhas,
            coalesce(sum(dotacao_inicial), 0) as inicial,
            coalesce(sum(dotacao_atualizada), 0) as atualizada
        from {{ ref("emendas_fato_dotacao") }}
    ),

    dotacao_silver as (
        select
            count(*) as linhas,
            coalesce(sum(dotacao_inicial), 0) as inicial,
            coalesce(sum(dotacao_atualizada), 0) as atualizada
        from {{ ref("emenda_dotacao") }}
    ),

    comparacao as (
        select 'execucao: linhas' as medida, f.linhas as fato, s.linhas as silver
        from execucao_fato as f, execucao_silver as s
        union all
        select 'execucao: empenhado', f.empenhado, s.empenhado
        from execucao_fato as f, execucao_silver as s
        union all
        select 'execucao: liquidado', f.liquidado, s.liquidado
        from execucao_fato as f, execucao_silver as s
        union all
        select 'execucao: pago', f.pago, s.pago
        from execucao_fato as f, execucao_silver as s
        union all
        select 'execucao: rap inscrito', f.rap_inscrito, s.rap_inscrito
        from execucao_fato as f, execucao_silver as s
        union all
        select 'execucao: rap pago', f.rap_pago, s.rap_pago
        from execucao_fato as f, execucao_silver as s
        union all
        select 'dotacao: linhas', f.linhas, s.linhas
        from dotacao_fato as f, dotacao_silver as s
        union all
        select 'dotacao: inicial', f.inicial, s.inicial
        from dotacao_fato as f, dotacao_silver as s
        union all
        select 'dotacao: atualizada', f.atualizada, s.atualizada
        from dotacao_fato as f, dotacao_silver as s
    )

select *
from comparacao
where fato <> silver
