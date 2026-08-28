{{ config(materialized="table") }}

with

    -- Lado SIAFI: valores mensais de empenhado/liquidado/pago/restos a pagar
    -- por contrato. Exclui linhas com mes_lancamento nulo: são contratos
    -- Ativos sem nenhum estágio SIAFI correspondente (originadas do full
    -- join final de contratos_estagios), sem mês para casar na série.
    siafi as (
        select
            contrato_id,
            mes_lancamento as mes_referencia,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            restos_a_pagar,
            restos_a_pagar_pago,
            estrategias_match,
            dt_ingest as dt_ingest_siafi
        from {{ ref("contratos_estagios") }}
        where contrato_id is not null and mes_lancamento is not null
    ),

    -- Lado Compras GOV: cronograma previsto e faturas pagas/pendentes por
    -- contrato e mês.
    compras_gov as (
        select
            contrato_id,
            mes_referencia,
            valor_cronograma,
            valor_faturas_pagas,
            valor_faturas_pendentes,
            saldo_contratual_disponivel
        from {{ ref("cronogramas_faturas_mensal") }}
        where contrato_id is not null
    ),

    -- 1) Full join SIAFI x Compras GOV por contrato_id + mes_referencia:
    -- mantém todo mês com movimentação em qualquer um dos dois lados.
    siafi_compras_gov as (
        select
            coalesce(s.contrato_id, cg.contrato_id) as contrato_id,
            coalesce(s.mes_referencia, cg.mes_referencia) as mes_referencia,
            s.valor_empenhado,
            s.valor_liquidado,
            s.valor_pago,
            s.restos_a_pagar,
            s.restos_a_pagar_pago,
            s.estrategias_match,
            cg.valor_cronograma,
            cg.valor_faturas_pagas,
            cg.valor_faturas_pendentes,
            cg.saldo_contratual_disponivel,
            s.dt_ingest_siafi
        from siafi as s
        full join
            compras_gov as cg
            on s.contrato_id = cg.contrato_id
            and s.mes_referencia = cg.mes_referencia
    ),

    -- 2) Full join com preenchimento_meses para garantir a série mensal
    -- contínua (sem lacunas) para cada contrato, mesmo em meses sem
    -- movimentação em nenhum dos dois lados.
    serie_completa as (
        select
            coalesce(scg.contrato_id, pm.contrato_id) as contrato_id,
            coalesce(scg.mes_referencia, pm.mes_referencia) as mes_referencia,
            scg.valor_empenhado,
            scg.valor_liquidado,
            scg.valor_pago,
            scg.restos_a_pagar,
            scg.restos_a_pagar_pago,
            scg.estrategias_match,
            coalesce(scg.valor_cronograma, pm.valor_cronograma) as valor_cronograma,
            coalesce(
                scg.valor_faturas_pagas, pm.valor_faturas_pagas
            ) as valor_faturas_pagas,
            coalesce(
                scg.valor_faturas_pendentes, pm.valor_faturas_pendentes
            ) as valor_faturas_pendentes,
            coalesce(
                scg.saldo_contratual_disponivel, pm.saldo_contratual_disponivel
            ) as saldo_contratual_disponivel,
            scg.dt_ingest_siafi
        from siafi_compras_gov as scg
        full join
            {{ ref("preenchimento_meses") }} as pm
            on scg.contrato_id = pm.contrato_id
            and scg.mes_referencia = pm.mes_referencia
    ),

    -- 3) Left join final com contratos para os dados cadastrais (número,
    -- fornecedor, órgão, vigência etc).
    final as (
        select
            sc.contrato_id,
            sc.mes_referencia,
            sc.valor_empenhado,
            sc.valor_liquidado,
            sc.valor_pago,
            sc.restos_a_pagar,
            sc.restos_a_pagar_pago,
            sc.estrategias_match,
            sc.valor_cronograma,
            sc.valor_faturas_pagas,
            sc.valor_faturas_pendentes,
            sc.saldo_contratual_disponivel,
            ct.numero as numero_contrato,
            ct.situacao as situacao_contrato,
            ct.fornecedor_nome,
            ct.fornecedor_cnpj_cpf_idgener,
            ct.contratante__orgao__nome as orgao_contratante,
            ct.contratante__orgao__unidade_gestora__nome as unidade_gestora,
            ct.objeto as objeto_contrato,
            ct.unidades_requisitantes,
            ct.vigencia_inicio,
            ct.vigencia_fim,
            greatest(sc.dt_ingest_siafi, ct.dt_ingest) as dt_ingest
        from serie_completa as sc
        left join {{ ref("contratos") }} as ct on sc.contrato_id = ct.id
    )

select *
from final
