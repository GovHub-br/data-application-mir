create or replace function parse_number(in_text text) returns numeric as $$
	select
		case when in_text like '(%' then regexp_replace(replace(coalesce(in_text, '0'), '.', ''), '(\()?(\d+),(\d+)(\))?', '-\2.\3')::numeric(15,2)
			else replace(replace(coalesce(in_text, '0'), '.', ''), ',', '.')::numeric(15,2) end as result
$$ language sql;

-- Comentário: O erro indica que há valores com parênteses "(660000.00)" que não podem ser convertidos para double precision
-- O erro está ocorrendo nas colunas de valores monetários, especificamente em:
-- - despesas_empenhadas_controle_empenho_saldo_moeda_origem
-- - despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem
-- - despesas_liquidadas_controle_empenho_saldo_moeda_origem 
-- - despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem
-- - despesas_pagas_controle_empenho_saldo_moeda_origem
-- - despesas_pagas_controle_empenho_movim_liquido_moeda_origem

-- Precisamos modificar o CAST dessas colunas para tratar valores entre parênteses como números negativos



WITH estagios_raw AS (
    SELECT
        id::INTEGER as id,
        ne_ccor,
        ne_informacao_complementar :: TEXT,

        -- Remove o "0" inicial e pontos, barras e hífens do número do processo
        CASE 
            WHEN LENGTH(ne_num_processo::text) > 3 THEN REGEXP_REPLACE(LTRIM(ne_num_processo::text, '0'), '[\./-]', '', 'g')
            ELSE ne_num_processo::text
        END AS ne_num_processo,

        ne_ccor_descricao :: TEXT,
        doc_observacao :: TEXT,

        CASE
            WHEN natureza_despesa::text ~ '^\d+$' THEN CAST(natureza_despesa AS INTEGER)
            ELSE NULL
        END AS natureza_despesa,

        natureza_despesa_1,

        CASE
            WHEN natureza_despesa_detalhada::text ~ '^\d+$' THEN CAST(natureza_despesa_detalhada AS INTEGER)
            ELSE NULL
        END AS natureza_despesa_detalhada,

        natureza_despesa_detalhada_1,
        ne_ccor_favorecido,
        ne_ccor_favorecido_1,

        CASE
            WHEN ano_lancamento::text ~ '^\d+$' THEN CAST(ano_lancamento AS INTEGER)
            ELSE NULL
        END AS ano_lancamento,

        ne_ccor_mes_emissao,

        CASE
            WHEN ne_ccor_ano_emissao::text ~ '^\d+$' THEN CAST(ne_ccor_ano_emissao AS INTEGER)
            ELSE NULL
        END AS ne_ccor_ano_emissao,

        mes_lancamento,
        parse_number(despesas_empenhadas_controle_empenho_saldo_moeda_origem) AS despesas_empenhadas_controle_empenho_saldo_moeda_origem,
        parse_number(despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem) AS despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem,
        parse_number(despesas_liquidadas_controle_empenho_saldo_moeda_origem) AS despesas_liquidadas_controle_empenho_saldo_moeda_origem,
        parse_number(despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem) AS despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem,
        parse_number(despesas_pagas_controle_empenho_saldo_moeda_origem) AS despesas_pagas_controle_empenho_saldo_moeda_origem,
        parse_number(despesas_pagas_controle_empenho_movim_liquido_moeda_origem) AS despesas_pagas_controle_empenho_movim_liquido_moeda_origem

    FROM raw.estagios
)

SELECT * FROM estagios_raw
