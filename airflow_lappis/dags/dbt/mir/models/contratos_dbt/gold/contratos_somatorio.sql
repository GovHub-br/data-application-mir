{{ config(materialized="table") }}

with

    -- Base mensal: um linha por contrato/mês vinda de contratos_comparativo_mensal,
    -- com o valor de faturas do mês (pagas + pendentes) já consolidado para
    -- viabilizar o cálculo de orcamento_a_executar.
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
            saldo_contratual_disponivel,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            dt_ingest
        from {{ ref("contratos_comparativo_mensal") }}
        where contrato_id is not null
    ),

    -- Indicador orcamento_a_executar: soma do valor de cronograma apenas nos
    -- meses em que não houve faturamento (pago ou pendente) para o contrato.
    orcamento_a_executar as (
        select contrato_id, coalesce(sum(valor_cronograma), 0) as orcamento_a_executar
        from comparativo_mensal
        where valor_faturas_mes = 0
        group by contrato_id
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
            coalesce(sum(saldo_contratual_disponivel), 0) as total_saldo_disponivel,
            coalesce(sum(valor_empenhado), 0) as total_empenhado,
            coalesce(sum(valor_liquidado), 0) as total_liquidado,
            coalesce(sum(valor_pago), 0) as total_pago,
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
    s.total_saldo_disponivel,
    s.total_empenhado,
    s.total_liquidado,
    s.total_pago,
    coalesce(oe.orcamento_a_executar, 0) as orcamento_a_executar,
    s.dt_ingest
from somatorio as s
left join orcamento_a_executar as oe on s.contrato_id = oe.contrato_id
