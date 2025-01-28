WITH 

valores_pagos_contratos AS (
  SELECT contrato_id AS id,
        SUM(despesas_pagas_movim_liquido) AS despesas_pagas
  -- FROM public_silver.silver_contratos_empenhos
  FROM {{ ref('contratos_empenhos')}}
  WHERE contrato_id IS NOT NULL
  GROUP BY contrato_id),
     
     
contratos_gold AS (
  SELECT *,
        CASE
            WHEN vp.despesas_pagas = c.valor_global THEN 'Sim'
            ELSE 'Não'
  END AS pendente_baixa
  -- FROM public_raw.contratos c
  FROM {{ ref('contratos')}}
  LEFT JOIN valores_pagos_contratos vp USING(id)) --

SELECT 
  id AS contrato_id,
  numero AS numero,
  modalidade AS modalidade,
  situacao AS situacao,
  pendente_baixa AS pendente_baixa,
  CONCAT(contratante_orgao_origem_unidade_gestora_origem_codigo, ' - ', contratante_orgao_origem_unidade_gestora_origem_nome_resumido) AS "Unidade",
  fornecedor_nome AS fornecedor_nome,
  objeto AS objeto,
  valor_global AS valor_global,
  despesas_pagas AS despesas_pagas,
  vigencia_inicio AS vigencia_inicio,
  vigencia_fim AS vigencia_fim
FROM contratos_gold