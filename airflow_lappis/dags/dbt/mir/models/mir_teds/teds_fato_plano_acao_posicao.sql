{{ config(alias="fato_plano_acao_posicao") }}

-- Posicao acumulada de cada plano de acao de TED (snapshot), uma linha por
-- plano. Valor firmado do TransfereGov; credito (NC) e financeiro (PF) da
-- silver; execucao das NEs do nucleo ligadas ao plano (nula sem NE).
with
    credito as (
        select
            id_plano_acao,
            sum(valor) filter (where tipo = 'Recebido') as credito_recebido,
            sum(valor) filter (where tipo = 'Devolvido') as credito_devolvido,
            sum(valor) filter (where tipo = 'Anulado') as credito_anulado,
            count(*) as qtd_nc
        from {{ ref("ted_credito_nc") }}
        where id_plano_acao is not null
        group by id_plano_acao
    ),

    financeiro as (
        select
            id_plano_acao,
            sum(valor) filter (where tipo = 'Transferência') as financeiro_recebido,
            sum(valor) filter (where tipo = 'Devolução') as financeiro_devolvido,
            count(*) as qtd_pf
        from {{ ref("ted_programacao_pf") }}
        where id_plano_acao is not null
        group by id_plano_acao
    ),

    -- RAP inscrito sem as reinscricoes: o saldo nao pago reaparece como
    -- inscrito no exercicio seguinte e nao pode ser somado de novo
    execucao as (
        select
            nr_instrumento::integer as id_plano_acao,
            sum(despesas_empenhadas) as despesas_empenhadas,
            sum(greatest(despesas_empenhadas, 0)) as empenhado_bruto,
            sum(greatest(- despesas_empenhadas, 0)) as empenho_anulado,
            sum(despesas_liquidadas) as despesas_liquidadas,
            sum(despesas_pagas) as despesas_pagas,
            sum(
                case when reinscricao_rap then 0 else restos_a_pagar_inscritos end
            ) as restos_a_pagar_inscritos_acumulavel,
            sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,
            count(distinct ne_ccor) as qtd_nes
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'TED'
        group by nr_instrumento
    )

select
    {{ fk(["p.id_plano_acao"]) }} as sk_plano_acao,

    -- Pactuado
    p.valor_firmado,
    p.valor_beneficiario_especifico,
    p.valor_chamamento_publico,

    -- Credito descentralizado (NC)
    coalesce(c.credito_recebido, 0) as credito_recebido,
    coalesce(c.credito_devolvido, 0) as credito_devolvido,
    coalesce(c.credito_anulado, 0) as credito_anulado,
    coalesce(c.qtd_nc, 0) as qtd_nc,

    -- Financeiro (PF)
    coalesce(f.financeiro_recebido, 0) as financeiro_recebido,
    coalesce(f.financeiro_devolvido, 0) as financeiro_devolvido,
    coalesce(f.qtd_pf, 0) as qtd_pf,

    -- Execucao SIAFI (nula sem NE)
    x.despesas_empenhadas,
    x.empenhado_bruto,
    x.empenho_anulado,
    x.despesas_liquidadas,
    x.despesas_pagas,
    x.restos_a_pagar_inscritos_acumulavel,
    x.restos_a_pagar_pagos,
    coalesce(x.qtd_nes, 0) as qtd_nes
from {{ ref("ted_plano_acao") }} as p
left join credito as c on c.id_plano_acao = p.id_plano_acao
left join financeiro as f on f.id_plano_acao = p.id_plano_acao
left join execucao as x on x.id_plano_acao = p.id_plano_acao
