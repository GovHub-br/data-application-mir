

WITH contratos_raw AS (
    SELECT
      -- Conversão de tipos e formatação de colunas
      CAST(id AS INT) AS id,
      receita_despesa,
      numero,
      CAST(contratante_orgao_origem_codigo AS INT) AS contratante_orgao_origem_codigo,
      contratante_orgao_origem_nome,
      CAST(contratante_orgao_origem_unidade_gestora_origem_codigo AS INT) AS contratante_orgao_origem_unidade_gestora_origem_codigo,
      contratante_orgao_origem_unidade_gestora_origem_nome_resumido,
      contratante_orgao_origem_unidade_gestora_origem_nome,
      contratante_orgao_origem_unidade_gestora_origem_sisg,
      contratante_orgao_origem_unidade_gestora_origem_utiliza_siafi,
      contratante_orgao_origem_unidade_gestora_origem_utiliza_antecip,
      CAST(contratante_orgao_codigo AS INT) AS contratante_orgao_codigo,
      contratante_orgao_nome,
      CAST(contratante_orgao_unidade_gestora_codigo AS INT) AS contratante_orgao_unidade_gestora_codigo,
      contratante_orgao_unidade_gestora_nome_resumido,
      contratante_orgao_unidade_gestora_nome,
      contratante_orgao_unidade_gestora_sisg,
      contratante_orgao_unidade_gestora_utiliza_siafi,
      contratante_orgao_unidade_gestora_utiliza_antecipagov,
      fornecedor_tipo,
      REGEXP_REPLACE(fornecedor_cnpj_cpf_idgener, '[^0-9A-Za-z]', '', 'g') AS fornecedor_cnpj_cpf_idgener,
      fornecedor_nome,
      CAST(codigo_tipo AS INT) AS codigo_tipo,
      tipo,
      subtipo,
      prorrogavel,
      situacao,
      justificativa_inativo,
      categoria,
      subcategoria,
      unidades_requisitantes,
      REGEXP_REPLACE(processo, '[^0-9A-Za-z]', '', 'g') AS processo,
      objeto,
      amparo_legal,
      informacao_complementar,
      codigo_modalidade,
      modalidade,
      CAST(unidade_compra AS INT) AS unidade_compra,
      licitacao_numero,
      sistema_origem_licitacao,

      -- Tratar valores nulos ou inválidos nas colunas de data
      CASE
          WHEN data_assinatura IS NULL THEN NULL
          WHEN data_assinatura IS NOT NULL AND data_assinatura::text ~ '^\d{4}-\d{2}-\d{2}$' THEN TO_DATE(data_assinatura::text, 'YYYY-MM-DD')
          ELSE NULL  -- Retorna NULL se não for uma data válida
      END AS data_assinatura,

      CASE
          WHEN data_publicacao IS NULL THEN NULL
          WHEN data_publicacao IS NOT NULL AND data_publicacao::text ~ '^\d{4}-\d{2}-\d{2}$' THEN TO_DATE(data_publicacao::text, 'YYYY-MM-DD')
          ELSE NULL  -- Retorna NULL se não for uma data válida
      END AS data_publicacao,

      CASE
          WHEN data_proposta_comercial IS NULL THEN NULL
          WHEN data_proposta_comercial IS NOT NULL AND data_proposta_comercial::text ~ '^\d{4}-\d{2}-\d{2}$' THEN TO_DATE(data_proposta_comercial::text, 'YYYY-MM-DD')
          ELSE NULL  -- Retorna NULL se não for uma data válida
      END AS data_proposta_comercial,

      CASE
          WHEN vigencia_inicio IS NULL THEN NULL
          WHEN vigencia_inicio IS NOT NULL AND vigencia_inicio::text ~ '^\d{4}-\d{2}-\d{2}$' THEN TO_DATE(vigencia_inicio::text, 'YYYY-MM-DD')
          ELSE NULL  -- Retorna NULL se não for uma data válida
      END AS vigencia_inicio,

      CASE
          WHEN vigencia_fim IS NULL THEN NULL
          WHEN vigencia_fim IS NOT NULL AND vigencia_fim::text ~ '^\d{4}-\d{2}-\d{2}$' THEN TO_DATE(vigencia_fim::text, 'YYYY-MM-DD')
          ELSE NULL  -- Retorna NULL se não for uma data válida
      END AS vigencia_fim,

      -- Conversão de valores numéricos para FLOAT ou INT
      REPLACE(REPLACE(valor_inicial::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS valor_inicial,
      REPLACE(REPLACE(valor_global::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS valor_global,
      CAST(num_parcelas AS INT) AS num_parcelas,
      REPLACE(REPLACE(valor_parcela::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS valor_parcela,
      REPLACE(REPLACE(valor_acumulado::TEXT, '.', ''), ',', '.')::NUMERIC(15, 2) AS valor_acumulado,

    FROM raw.contratos
)

SELECT * FROM contratos_raw
