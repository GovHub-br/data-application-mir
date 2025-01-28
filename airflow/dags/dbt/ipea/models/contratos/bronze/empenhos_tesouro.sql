create or replace function parse_number(in_text text) returns numeric as $$
	select
		case when in_text like '(%' then regexp_replace(replace(coalesce(in_text, '0'), '.', ''), '(\()?(\d+),(\d+)(\))?', '-\2.\3')::numeric(15,2)
			else replace(replace(coalesce(in_text, '0'), '.', ''), ',', '.')::numeric(15,2) end as result
$$ language sql;

WITH 

empenhos_raw AS (
    SELECT
        id::INTEGER AS id,
        ne_ccor::TEXT AS ne_ccor,
        ne_informacao_complementar::TEXT AS ne_informacao_complementar,
        REGEXP_REPLACE(ne_num_processo, '[./-]', '') AS ne_num_processo,
        ne_ccor_descricao::TEXT AS ne_ccor_descricao,
        doc_observacao::TEXT AS doc_observacao,
        natureza_despesa::INTEGER AS natureza_despesa,
        natureza_despesa_1::TEXT AS natureza_despesa_1,
        natureza_despesa_detalhada::INTEGER AS natureza_despesa_detalhada,
        natureza_despesa_detalhada_1::TEXT AS natureza_despesa_detalhada_1,
        ne_ccor_favorecido::TEXT AS ne_ccor_favorecido,
        ne_ccor_favorecido_1::TEXT AS ne_ccor_favorecido_1,
        ne_ccor_ano_emissao::INTEGER AS ne_ccor_ano_emissao,
        item_informacao::INTEGER AS ne_ccor_ano_emissao_1,
        -- Aplicando NULLIF e removendo parênteses antes de converter para NUMERIC
        parse_number(despesas_empenhadas_controle_empenho_saldo_moeda_origem) AS despesas_empenhadas_saldo,
        parse_number(despesas_empenhadas_controle_empenho_movim_liquido_moeda_origem) AS despesas_empenhadas_movim_liquido,
        parse_number(despesas_liquidadas_controle_empenho_saldo_moeda_origem) AS despesas_liquidadas_saldo,
        parse_number(despesas_liquidadas_controle_empenho_movim_liquido_moeda_origem) AS despesas_liquidadas_movim_liquido,
        parse_number(despesas_pagas_controle_empenho_saldo_moeda_origem) AS despesas_pagas_saldo,
        parse_number(despesas_pagas_controle_empenho_movim_liquido_moeda_origem) AS despesas_pagas_movim_liquido
    FROM raw.empenhos_tesouro
    WHERE ne_ccor != 'Total'
)

SELECT * FROM empenhos_raw