-- Comentário: O erro indica que há valores com parênteses "(660000.00)" que não podem
-- ser convertidos para double precision
-- O erro está ocorrendo nas colunas de valores monetários, especificamente em:
-- - despesas_empenhadas_controle_empenho_saldo_moeda_origem
-- - despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem
-- - despesas_liquidadas_controle_empenho_saldo_moeda_origem 
-- - despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem
-- - despesas_pagas_controle_empenho_saldo_moeda_origem
-- - despesas_pagas_controle_empenho_movim_liquido_moeda_origem
-- Precisamos modificar o CAST dessas colunas para tratar valores entre parênteses como
-- números negativos
with
    estagios_raw as (
        select
            id::integer as id,
            ne_ccor,
            ne_informacao_complementar::text,

            -- Remove o "0" inicial e pontos, barras e hífens do número do processo
            case
                when length(ne_num_processo::text) > 3
                then regexp_replace(ltrim(ne_num_processo::text, '0'), '[\./-]', '', 'g')
                else ne_num_processo::text
            end as ne_num_processo,

            ne_ccor_descricao::text,
            doc_observacao::text,

            case
                when natureza_despesa::text ~ '^\d+$'
                then cast(natureza_despesa as integer)
                else null
            end as natureza_despesa,

            natureza_despesa_1,

            case
                when natureza_despesa_detalhada::text ~ '^\d+$'
                then cast(natureza_despesa_detalhada as integer)
                else null
            end as natureza_despesa_detalhada,

            natureza_despesa_detalhada_1,
            ne_ccor_favorecido,
            ne_ccor_favorecido_1,

            case
                when ano_lancamento::text ~ '^\d+$'
                then cast(ano_lancamento as integer)
                else null
            end as ano_lancamento,

            ne_ccor_mes_emissao,

            case
                when ne_ccor_ano_emissao::text ~ '^\d+$'
                then cast(ne_ccor_ano_emissao as integer)
                else null
            end as ne_ccor_ano_emissao,

            mes_lancamento,
            {{ target.schema }}.parse_number(
                despesas_empenhadas_controle_empenho_saldo_moeda_origem
            ) as despesas_empenhadas_controle_empenho_saldo_moeda_origem,
            {{ target.schema }}.parse_number(
                despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem
            ) as despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem,
            {{ target.schema }}.parse_number(
                despesas_liquidadas_controle_empenho_saldo_moeda_origem
            ) as despesas_liquidadas_controle_empenho_saldo_moeda_origem,
            {{ target.schema }}.parse_number(
                despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem
            ) as despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem,
            {{ target.schema }}.parse_number(
                despesas_pagas_controle_empenho_saldo_moeda_origem
            ) as despesas_pagas_controle_empenho_saldo_moeda_origem,
            {{ target.schema }}.parse_number(
                despesas_pagas_controle_empenho_movim_liquido_moeda_origem
            ) as despesas_pagas_controle_empenho_movim_liquido_moeda_origem

        from {{ source("siafi", "estagios") }}
    )

select *
from estagios_raw
