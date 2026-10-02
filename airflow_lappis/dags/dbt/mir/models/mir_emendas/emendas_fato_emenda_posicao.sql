{{ config(alias="fato_emenda_posicao") }}

-- Posicao acumulada de cada emenda (snapshot), uma linha por emenda com
-- dotacao ou NE: dotacao (soma dos movimentos), execucao das NEs de emenda e
-- quantidade de NEs e de instrumentos. Execucao 0 quando a emenda so tem
-- dotacao (dinheiro reservado e ainda nao empenhado).
with
    dotacao as (
        select
            codigo_emenda,
            sum(dotacao_inicial) as dotacao_inicial,
            sum(dotacao_atualizada) as dotacao_atualizada
        from {{ ref("emenda_dotacao") }}
        group by codigo_emenda
    ),

    -- RAP inscrito sem as reinscricoes: o saldo nao pago reaparece como
    -- inscrito no exercicio seguinte e nao pode ser somado de novo
    execucao as (
        select
            codigo_emenda,
            sum(despesas_empenhadas) as despesas_empenhadas,
            sum(despesas_liquidadas) as despesas_liquidadas,
            sum(despesas_pagas) as despesas_pagas,
            sum(
                case when reinscricao_rap then 0 else restos_a_pagar_inscritos end
            ) as restos_a_pagar_inscritos_acumulavel,
            sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,
            count(distinct ne_ccor) as qtd_nes,
            count(
                distinct case
                    when sistema_instrumento <> 'Não identificado'
                    then sistema_instrumento || '|' || nr_instrumento
                end
            ) as qtd_instrumentos
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
        group by codigo_emenda
    ),

    emendas as (
        select codigo_emenda
        from dotacao
        union
        select codigo_emenda
        from execucao
    )

select
    {{ fk(["e.codigo_emenda"]) }} as sk_emenda,
    coalesce(d.dotacao_inicial, 0) as dotacao_inicial,
    coalesce(d.dotacao_atualizada, 0) as dotacao_atualizada,
    coalesce(x.despesas_empenhadas, 0) as despesas_empenhadas,
    coalesce(x.despesas_liquidadas, 0) as despesas_liquidadas,
    coalesce(x.despesas_pagas, 0) as despesas_pagas,
    coalesce(
        x.restos_a_pagar_inscritos_acumulavel, 0
    ) as restos_a_pagar_inscritos_acumulavel,
    coalesce(x.restos_a_pagar_pagos, 0) as restos_a_pagar_pagos,
    coalesce(x.qtd_nes, 0) as qtd_nes,
    coalesce(x.qtd_instrumentos, 0) as qtd_instrumentos
from emendas as e
left join dotacao as d on d.codigo_emenda = e.codigo_emenda
left join execucao as x on x.codigo_emenda = e.codigo_emenda
