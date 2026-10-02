-- Posicao acumulada de cada convenio do MIR (snapshot), uma linha por
-- convenio. Os valores pactuados vem do SICONV; movimentos, eventos e
-- contagens, da silver; a execucao orcamentaria, do nucleo SIAFI.
-- Empenhado aparece de duas fontes: o registro do SICONV (historico completo,
-- mesma medida do gold antigo) e as NEs do relatorio do Tesouro (so os
-- exercicios cobertos, com liquidado, pago e RAP; nulas sem NE).
with
    movimentos as (
        select
            nr_convenio,
            sum(valor) filter (
                where tipo_movimento = 'Desembolso federal'
            ) as valor_desembolsado,
            count(*) filter (
                where tipo_movimento = 'Desembolso federal'
            ) as qtd_desembolsos,
            sum(valor) filter (
                where tipo_movimento = 'Contrapartida depositada'
            ) as valor_contrapartida_depositada,
            sum(valor) filter (
                where tipo_movimento = 'Desbloqueio'
            ) as valor_desbloqueado,
            sum(valor_bloqueado) filter (
                where tipo_movimento = 'Desbloqueio'
            ) as valor_bloqueado,
            sum(valor) filter (
                where tipo_movimento = 'Pagamento a fornecedor'
            ) as valor_pago_fornecedores,
            count(*) filter (
                where tipo_movimento = 'Pagamento a fornecedor'
            ) as qtd_pagamentos,
            max(data_movimento) filter (
                where tipo_movimento = 'Pagamento a fornecedor'
            ) as data_ultimo_pagamento,
            sum(valor) filter (
                where tipo_movimento = 'Pagamento de tributo'
            ) as valor_tributos,
            count(*) filter (
                where tipo_movimento = 'Pagamento de tributo'
            ) as qtd_pagamentos_tributo
        from {{ ref("convenio_movimento_financeiro") }}
        group by nr_convenio
    ),

    eventos as (
        select
            nr_convenio,
            count(*) filter (where tipo_evento = 'Termo aditivo') as qtd_aditivos,
            count(*) filter (
                where tipo_evento = 'Prorrogação de ofício'
            ) as qtd_prorrogacoes
        from {{ ref("convenio_evento") }}
        group by nr_convenio
    ),

    -- RAP inscrito sem as reinscricoes: o saldo nao pago reaparece como
    -- inscrito no exercicio seguinte e nao pode ser somado de novo
    execucao as (
        select
            nr_instrumento as nr_convenio,
            sum(despesas_empenhadas) as despesas_empenhadas,
            sum(despesas_liquidadas) as despesas_liquidadas,
            sum(despesas_pagas) as despesas_pagas,
            sum(
                case when reinscricao_rap then 0 else restos_a_pagar_inscritos end
            ) as restos_a_pagar_inscritos_acumulavel,
            sum(restos_a_pagar_pagos) as restos_a_pagar_pagos
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV'
        group by nr_instrumento
    )

select
    {{ fk(["c.nr_convenio"]) }} as sk_convenio,
    {{ fk(["c.convenente_documento"]) }} as sk_convenente,
    {{ fk(["coalesce(c.cod_municipio_ibge, 'UF-' || c.uf)"]) }} as sk_localidade,

    -- Pactuado
    c.valor_global_original as valor_firmado_inicial,
    c.valor_global as valor_firmado_atualizado,
    c.valor_repasse as valor_repasse_previsto,
    c.valor_contrapartida as valor_contrapartida_prevista,
    c.valor_saldo_conta,

    -- Movimentos financeiros
    coalesce(m.valor_desembolsado, 0) as valor_desembolsado,
    coalesce(m.qtd_desembolsos, 0) as qtd_desembolsos,
    k.data_ultimo_desembolso,
    coalesce(m.valor_contrapartida_depositada, 0) as valor_contrapartida_depositada,
    coalesce(m.valor_desbloqueado, 0) as valor_desbloqueado,
    coalesce(m.valor_bloqueado, 0) as valor_bloqueado,
    coalesce(m.valor_pago_fornecedores, 0) as valor_pago_fornecedores,
    coalesce(m.qtd_pagamentos, 0) as qtd_pagamentos,
    m.data_ultimo_pagamento,
    coalesce(m.valor_tributos, 0) as valor_tributos,
    coalesce(m.qtd_pagamentos_tributo, 0) as qtd_pagamentos_tributo,

    -- Empenhado registrado no SICONV (historico completo)
    k.valor_empenhado_siconv,
    k.qtd_empenhos_siconv,

    -- Execucao SIAFI (NEs do relatorio do Tesouro; nulo sem NE)
    x.despesas_empenhadas,
    x.despesas_liquidadas,
    x.despesas_pagas,
    x.restos_a_pagar_inscritos_acumulavel,
    x.restos_a_pagar_pagos,

    -- Contagens
    k.qtd_metas,
    k.qtd_licitacoes,
    k.valor_licitado,
    coalesce(e.qtd_aditivos, 0) as qtd_aditivos,
    coalesce(e.qtd_prorrogacoes, 0) as qtd_prorrogacoes
from {{ ref("convenio_mir") }} as c
left join movimentos as m on m.nr_convenio = c.nr_convenio
left join eventos as e on e.nr_convenio = c.nr_convenio
left join execucao as x on x.nr_convenio = c.nr_convenio
left join {{ ref("convenio_contagens") }} as k on k.nr_convenio = c.nr_convenio
