{{ config(materialized="table") }}


with
    empenhos_tesouro_raw as (
        select
            programa_governo::text as programa_governo,
            programa_governo_descricao::text as programa_governo_descricao,
            acao_governo::text as acao_governo,
            acao_governo_descricao::text as acao_governo_descricao,
            emissao_mes::text as emissao_mes,
            emissao_dia::text as emissao_dia,
            ne_ccor::text as ne_ccor,
            -- No relatório PPA só a linha de emissão da NE traz o processo; as
            -- de liquidação e pagamento vêm com o sentinela '-9'. Propaga o
            -- processo da NE para todas as linhas dela (cada NE tem no máximo
            -- um processo real), senão a estratégia por processo de
            -- contratos_empenhos casa só a emissão e perde os pagamentos.
            max(
                case
                    when ne_num_processo <> '-9'
                    then regexp_replace(ne_num_processo, '[./-]', '', 'g')
                end
            ) over (partition by ne_ccor) as ne_num_processo,
            ne_info_complementar::text as ne_info_complementar,
            ne_ccor_descricao::text as ne_ccor_descricao,
            doc_observacao::text as doc_observacao,
            natureza_despesa::text as natureza_despesa,
            natureza_despesa_descricao::text as natureza_despesa_descricao,
            upper(ne_ccor_favorecido::text) as ne_ccor_favorecido,
            ne_ccor_favorecido_descricao::text as ne_ccor_favorecido_descricao,
            ne_ccor_ano_emissao::integer as ne_ccor_ano_emissao,
            ptres::text as ptres,
            fonte_recursos_detalhada::text as fonte_recursos_detalhada,
            fonte_recursos_detalhada_descricao::text as fonte_recursos_detalhada_descricao,
            {{ parse_financial_value("despesas_empenhadas") }} as despesas_empenhadas,
            {{ parse_financial_value("despesas_liquidadas") }} as despesas_liquidadas,
            {{ parse_financial_value("despesas_pagas") }} as despesas_pagas,
            {{ parse_financial_value("restos_a_pagar_inscritos") }} as restos_a_pagar_inscritos,
            {{ parse_financial_value("restos_a_pagar_pagos") }} as restos_a_pagar_pagos,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        -- Relatório "Notas de empenhos por programa PPA". O ne_tesouro foi
        -- abandonado por estar defasado e com buracos (sem a UG 230002).
        -- ne_ccor = '-9' é o grão de dotação, sem empenho; fica de fora.
        from {{ source("siafi", "ne_tesouro_ppa") }}
        where ne_ccor <> '-9'
            and ne_ccor_ano_emissao ~ '^[0-9]{4}$'
            and (
                left(ne_ccor, 6) in ('230002', '810008')
                -- NEs que a API de contratos vincula a um contrato do MIR,
                -- de qualquer UG (ex.: 810005, que empenhou contratos do MIR
                -- em 2023).
                or ne_ccor in (
                    select unidade_gestora || gestao || upper(numero)
                    from {{ source("compras_gov", "empenhos") }}
                )
            )
    )

select *
from empenhos_tesouro_raw
