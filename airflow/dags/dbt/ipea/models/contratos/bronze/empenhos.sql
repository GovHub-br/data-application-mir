WITH empenhos AS (
    SELECT
        id::TEXT AS id,
        contrato_id::TEXT AS contrato_id,
        unidade_gestora,
        gestao,
        numero AS nota_empenho,
        credor,
        fonte_recurso,
        programa_trabalho,
        planointerno,
        naturezadespesa,
        informacao_complementar,
        sistema_origem,
        links_documento_pagamento,
        credor_obj_tipo,
        credor_obj_cnpj_cpf_idgener,
        credor_obj_nome,

    -- Tratar valores nulos ou inválidos nas colunas de data
        CASE
            WHEN data_emissao IS NOT NULL AND data_emissao::text ~ '^\d{4}-\d{2}-\d{2}$' THEN TO_DATE(data_emissao::text, 'YYYY-MM-DD')
            ELSE NULL  -- Retorna NULL se não for uma data válida
        END AS data_emissao,

    -- Conversão de valores numéricos para FLOAT
        REPLACE(REPLACE(empenhado::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS empenhado,
        REPLACE(REPLACE(aliquidar::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS aliquidar,
        REPLACE(REPLACE(liquidado::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS liquidado,
        REPLACE(REPLACE(pago::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS pago,
        REPLACE(REPLACE(rpinscrito::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS rpinscrito,
        REPLACE(REPLACE(rpaliquidar::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS rpaliquidar,
        REPLACE(REPLACE(rpliquidado::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS rpliquidado,
        REPLACE(REPLACE(rppago::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS rppago

    FROM raw.empenhos         
)
SELECT * FROM empenhos