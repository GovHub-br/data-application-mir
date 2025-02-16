with

    empenhos_raw as (
        select
            id::integer as id,
            ne_ccor::text as ne_ccor,
            ne_informacao_complementar::text as ne_informacao_complementar,
            ne_ccor_descricao::text as ne_ccor_descricao,
            doc_observacao::text as doc_observacao,
            natureza_despesa::integer as natureza_despesa,
            natureza_despesa_1::text as natureza_despesa_1,
            natureza_despesa_detalhada::integer as natureza_despesa_detalhada,
            natureza_despesa_detalhada_1::text as natureza_despesa_detalhada_1,
            ne_ccor_favorecido::text as ne_ccor_favorecido,
            ne_ccor_favorecido_1::text as ne_ccor_favorecido_1,
            ne_ccor_ano_emissao::integer as ne_ccor_ano_emissao,
            item_informacao::integer as ne_ccor_ano_emissao_1,
            regexp_replace(ne_num_processo, '[./-]', '') as ne_num_processo,
            -- Aplicando NULLIF e removendo parênteses antes de converter para NUMERIC
            {{ target.schema }}.parse_number(
                despesas_empenhadas_controle_empenho_saldo_moeda_origem
            ) as despesas_empenhadas_saldo,
            {{ target.schema }}.parse_number(
                despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem
            ) as despesas_empenhadas_movim_liquido,
            {{ target.schema }}.parse_number(
                despesas_liquidadas_controle_empenho_saldo_moeda_origem
            ) as despesas_liquidadas_saldo,
            {{ target.schema }}.parse_number(
                despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem
            ) as despesas_liquidadas_movim_liquido,
            {{ target.schema }}.parse_number(
                despesas_pagas_controle_empenho_saldo_moeda_origem
            ) as despesas_pagas_saldo,
            {{ target.schema }}.parse_number(
                despesas_pagas_controle_empenho_movim_liquido_moeda_origem
            ) as despesas_pagas_movim_liquido
        from {{ source("siafi", "empenhos_tesouro") }}
        where ne_ccor != 'Total'
    )

select *
from empenhos_raw
