

WITH faturas_raw AS (
    SELECT
        id::INTEGER AS id,
        contrato_id::INTEGER AS contrato_id,
        tipolistafatura_id::TEXT AS tipolistafatura_id,
        justificativafatura_id::TEXT AS justificativafatura_id,
        sfadrao_id::TEXT AS sfadrao_id,
        numero::TEXT AS numero,
        emissao::DATE AS emissao,
        prazo::DATE AS prazo,
        vencimento::DATE AS vencimento,
        -- Limpar o formato numérico das colunas que têm problemas
        REPLACE(REPLACE(valor::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS valor,
        REPLACE(REPLACE(juros::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS juros,
        REPLACE(REPLACE(multa::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS multa,
        REPLACE(REPLACE(glosa::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS glosa,
        REPLACE(REPLACE(valorliquido::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS valorliquido,
        processo::TEXT AS processo,
        protocolo::DATE AS protocolo,
        ateste::DATE AS ateste,
        repactuacao::TEXT AS repactuacao,
        infcomplementar::TEXT AS infcomplementar,
        mesref::INTEGER AS mesref,
        anoref::INTEGER AS anoref,
        situacao::TEXT AS situacao,
        chave_nfe::TEXT AS chave_nfe,
        jsonb_array_elements(dados_empenho::jsonb) AS dados_empenho,
        dados_referencia::TEXT AS dados_referencia,
        dados_item_faturado::TEXT AS dados_item_faturado
    FROM raw.faturas
),

-- Extrai os campos do JSON e transforma em colunas individuais
faturas_dados_empenho AS (
    SELECT
        f.*,
        dados_empenho->>'id_empenho' AS id_empenho,
        upper(dados_empenho->>'numero_empenho') AS numero_empenho,
        dados_empenho->>'valor_empenho' AS valor_empenho,
        dados_empenho->>'subelemento' AS subelemento
    FROM faturas_raw AS f
)

--

SELECT *
FROM faturas_dados_empenho 
