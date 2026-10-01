{{ config(materialized="table") }}

with

    -- Base mensal: um linha por contrato/mês vinda de contratos_comparativo_mensal,
    -- com o valor de faturas do mês (pagas + pendentes) já consolidado.
    comparativo_mensal as (
        select
            contrato_id,
            numero_contrato,
            fornecedor_cnpj_cpf_idgener,
            fornecedor_tipo,
            fornecedor_nome,
            valor_cronograma,
            coalesce(valor_faturas_pagas, 0)
            + coalesce(valor_faturas_pendentes, 0) as valor_faturas_mes,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            restos_a_pagar_pago,
            dt_ingest
        from {{ ref("contratos_comparativo_mensal") }}
        where contrato_id is not null
    ),

    -- Agregação por contrato dos totais usados nos indicadores de execução
    -- orçamentária e financeira.
    somatorio as (
        select
            contrato_id,
            numero_contrato,
            fornecedor_cnpj_cpf_idgener,
            fornecedor_tipo,
            fornecedor_nome,
            coalesce(sum(valor_cronograma), 0) as total_cronograma,
            coalesce(sum(valor_faturas_mes), 0) as total_faturas,
            coalesce(sum(valor_empenhado), 0) as total_empenhado,
            coalesce(sum(valor_liquidado), 0) as total_liquidado,
            -- Pago total: o do exercício mais o de restos a pagar (RAP).
            coalesce(sum(valor_pago), 0)
            + coalesce(sum(restos_a_pagar_pago), 0) as total_pago,
            max(dt_ingest) as dt_ingest
        from comparativo_mensal
        group by
            contrato_id,
            numero_contrato,
            fornecedor_cnpj_cpf_idgener,
            fornecedor_tipo,
            fornecedor_nome
    )

select
    s.contrato_id,
    s.numero_contrato,
    s.fornecedor_cnpj_cpf_idgener,
    s.fornecedor_tipo,
    s.fornecedor_nome,
    s.total_cronograma,
    s.total_faturas,
    -- Saldo do contrato ainda não empenhado: o cronograma (que acompanha o
    -- valor_acumulado do contrato) menos o empenhado no SIAFI. Contratos sem
    -- cronograma (pagamento único, com a NE no lugar do contrato) ficam com
    -- saldo zero. Nos demais, o saldo negativo é mantido de propósito: indica
    -- empenho acima do cronograma (ex.: reforço sem aditivo no Compras GOV).
    case
        when s.total_cronograma = 0
        then 0
        else s.total_cronograma - s.total_empenhado
    end as total_saldo_disponivel,
    s.total_empenhado,
    s.total_liquidado,
    s.total_pago,
    -- Empenhado ainda não pago (o pago já inclui o RAP).
    s.total_empenhado - s.total_pago as orcamento_a_executar,
    s.dt_ingest
from somatorio as s
