WITH contratos_unicos AS (
    -- Seleciona apenas os registros onde o fornecedor_cnpj_cpf_idgener é único
    SELECT * 
    FROM public_raw.contratos 
    WHERE fornecedor_cnpj_cpf_idgener IN     
        (SELECT fornecedor_cnpj_cpf_idgener 
         FROM public_raw.contratos 
         GROUP BY fornecedor_cnpj_cpf_idgener 
         HAVING COUNT(fornecedor_cnpj_cpf_idgener) = 1)
),

processos_unicos AS (
    -- Seleciona apenas os registros onde o processo é único e não está em contratos_unicos
    SELECT * 
    FROM public_raw.contratos 
    WHERE processo IN     
        (SELECT processo 
         FROM public_raw.contratos 
         GROUP BY processo 
         HAVING COUNT(processo) = 1)
),

numeros_unicos AS (
    -- Seleciona apenas os registros onde o numero é único e não está em contratos_unicos ou processos_unicos
    SELECT * 
    FROM public_raw.contratos 
    WHERE numero IN     
        (SELECT numero 
         FROM public_raw.contratos 
         GROUP BY numero 
         HAVING COUNT(numero) = 1)
),

faturas_contratos AS (
    -- Seleciona uma única correspondência de cada fatura
    SELECT DISTINCT ON (f.contrato_id) 
        f.numero_empenho,
        f.contrato_id,
        c.*
    FROM public_raw.faturas f
    JOIN public_raw.contratos c ON f.contrato_id = c.id
),

empenhos_contratos AS (
    -- Para cada empenho, seleciona apenas uma correspondência de contrato com prioridade na ordem definida
    SELECT 
        ec.*,                     
        COALESCE(c1.id, c2.id, c3.id, f.contrato_id, c_modalidade.id) AS contrato_id,
        COALESCE(c1.receita_despesa, c2.receita_despesa, c3.receita_despesa, f.receita_despesa, c_modalidade.receita_despesa) AS receita_despesa,
        COALESCE(c1.numero, c2.numero, c3.numero, f.numero,  c_modalidade.numero) AS numero,
        COALESCE(c1.contratante_orgao_origem_codigo, c2.contratante_orgao_origem_codigo, c3.contratante_orgao_origem_codigo, f.contratante_orgao_origem_codigo, c_modalidade.contratante_orgao_origem_codigo) AS contratante_orgao_origem_codigo,
        COALESCE(c1.contratante_orgao_origem_nome, c2.contratante_orgao_origem_nome, c3.contratante_orgao_origem_nome, f.contratante_orgao_origem_nome, c_modalidade.contratante_orgao_origem_nome) AS contratante_orgao_origem_nome,
        COALESCE(c1.contratante_orgao_origem_unidade_gestora_origem_codigo, c2.contratante_orgao_origem_unidade_gestora_origem_codigo, c3.contratante_orgao_origem_unidade_gestora_origem_codigo, f.contratante_orgao_origem_unidade_gestora_origem_codigo, c_modalidade.contratante_orgao_origem_unidade_gestora_origem_codigo) AS contratante_orgao_origem_unidade_gestora_origem_codigo,
        COALESCE(c1.contratante_orgao_origem_unidade_gestora_origem_nome_resumido, c2.contratante_orgao_origem_unidade_gestora_origem_nome_resumido, c3.contratante_orgao_origem_unidade_gestora_origem_nome_resumido, f.contratante_orgao_origem_unidade_gestora_origem_nome_resumido, c_modalidade.contratante_orgao_origem_unidade_gestora_origem_nome_resumido) AS contratante_orgao_origem_unidade_gestora_origem_nome_resumido,
        COALESCE(c1.contratante_orgao_origem_unidade_gestora_origem_nome, c2.contratante_orgao_origem_unidade_gestora_origem_nome, c3.contratante_orgao_origem_unidade_gestora_origem_nome, f.contratante_orgao_origem_unidade_gestora_origem_nome, c_modalidade.contratante_orgao_origem_unidade_gestora_origem_nome) AS contratante_orgao_origem_unidade_gestora_origem_nome,
        COALESCE(c1.contratante_orgao_origem_unidade_gestora_origem_sisg, c2.contratante_orgao_origem_unidade_gestora_origem_sisg, c3.contratante_orgao_origem_unidade_gestora_origem_sisg, f.contratante_orgao_origem_unidade_gestora_origem_sisg, c_modalidade.contratante_orgao_origem_unidade_gestora_origem_sisg) AS contratante_orgao_origem_unidade_gestora_origem_sisg,
        COALESCE(c1.contratante_orgao_origem_unidade_gestora_origem_utiliza_siafi, c2.contratante_orgao_origem_unidade_gestora_origem_utiliza_siafi, c3.contratante_orgao_origem_unidade_gestora_origem_utiliza_siafi, f.contratante_orgao_origem_unidade_gestora_origem_utiliza_siafi, c_modalidade.contratante_orgao_origem_unidade_gestora_origem_utiliza_siafi) AS contratante_orgao_origem_unidade_gestora_origem_utiliza_siafi,
        COALESCE(c1.contratante_orgao_origem_unidade_gestora_origem_utiliza_antecip, c2.contratante_orgao_origem_unidade_gestora_origem_utiliza_antecip, c3.contratante_orgao_origem_unidade_gestora_origem_utiliza_antecip, f.contratante_orgao_origem_unidade_gestora_origem_utiliza_antecip, c_modalidade.contratante_orgao_origem_unidade_gestora_origem_utiliza_antecip) AS contratante_orgao_origem_unidade_gestora_origem_utiliza_antecip,
        COALESCE(c1.contratante_orgao_codigo, c2.contratante_orgao_codigo, c3.contratante_orgao_codigo, f.contratante_orgao_codigo, c_modalidade.contratante_orgao_codigo) AS contratante_orgao_codigo,
        COALESCE(c1.contratante_orgao_nome, c2.contratante_orgao_nome, c3.contratante_orgao_nome, f.contratante_orgao_nome, c_modalidade.contratante_orgao_nome) AS contratante_orgao_nome,
        COALESCE(c1.contratante_orgao_unidade_gestora_codigo, c2.contratante_orgao_unidade_gestora_codigo, c3.contratante_orgao_unidade_gestora_codigo, f.contratante_orgao_unidade_gestora_codigo, c_modalidade.contratante_orgao_unidade_gestora_codigo) AS contratante_orgao_unidade_gestora_codigo,
        COALESCE(c1.contratante_orgao_unidade_gestora_nome_resumido, c2.contratante_orgao_unidade_gestora_nome_resumido, c3.contratante_orgao_unidade_gestora_nome_resumido, f.contratante_orgao_unidade_gestora_nome_resumido, c_modalidade.contratante_orgao_unidade_gestora_nome_resumido) AS contratante_orgao_unidade_gestora_nome_resumido,
        COALESCE(c1.contratante_orgao_unidade_gestora_nome, c2.contratante_orgao_unidade_gestora_nome, c3.contratante_orgao_unidade_gestora_nome, f.contratante_orgao_unidade_gestora_nome, c_modalidade.contratante_orgao_unidade_gestora_nome) AS contratante_orgao_unidade_gestora_nome,
        COALESCE(c1.contratante_orgao_unidade_gestora_sisg, c2.contratante_orgao_unidade_gestora_sisg, c3.contratante_orgao_unidade_gestora_sisg, f.contratante_orgao_unidade_gestora_sisg, c_modalidade.contratante_orgao_unidade_gestora_sisg) AS contratante_orgao_unidade_gestora_sisg,
        COALESCE(c1.contratante_orgao_unidade_gestora_utiliza_siafi, c2.contratante_orgao_unidade_gestora_utiliza_siafi, c3.contratante_orgao_unidade_gestora_utiliza_siafi, f.contratante_orgao_unidade_gestora_utiliza_siafi, c_modalidade.contratante_orgao_unidade_gestora_utiliza_siafi) AS contratante_orgao_unidade_gestora_utiliza_siafi,
        COALESCE(c1.contratante_orgao_unidade_gestora_utiliza_antecipagov, c2.contratante_orgao_unidade_gestora_utiliza_antecipagov, c3.contratante_orgao_unidade_gestora_utiliza_antecipagov, f.contratante_orgao_unidade_gestora_utiliza_antecipagov, c_modalidade.contratante_orgao_unidade_gestora_utiliza_antecipagov, f.contratante_orgao_unidade_gestora_utiliza_antecipagov) AS contratante_orgao_unidade_gestora_utiliza_antecipagov,
        COALESCE(c1.fornecedor_tipo, c2.fornecedor_tipo, c3.fornecedor_tipo, f.fornecedor_tipo, c_modalidade.fornecedor_tipo) AS fornecedor_tipo,
        COALESCE(c1.fornecedor_cnpj_cpf_idgener, c2.fornecedor_cnpj_cpf_idgener, c3.fornecedor_cnpj_cpf_idgener, f.fornecedor_cnpj_cpf_idgener, c_modalidade.fornecedor_cnpj_cpf_idgener) AS fornecedor_cnpj_cpf_idgener,
        COALESCE(c1.fornecedor_nome, c2.fornecedor_nome, c3.fornecedor_nome, f.fornecedor_nome, c_modalidade.fornecedor_nome) AS fornecedor_nome,
        COALESCE(c1.codigo_tipo, c2.codigo_tipo, c3.codigo_tipo, f.codigo_tipo, c_modalidade.codigo_tipo) AS codigo_tipo,
        COALESCE(c1.tipo, c2.tipo, c3.tipo, f.tipo, c_modalidade.tipo) AS tipo,
        COALESCE(c1.subtipo, c2.subtipo, c3.subtipo, f.subtipo, c_modalidade.subtipo) AS subtipo,
        COALESCE(c1.prorrogavel, c2.prorrogavel, c3.prorrogavel, f.prorrogavel, c_modalidade.prorrogavel) AS prorrogavel,
        COALESCE(c1.situacao, c2.situacao, c3.situacao, f.situacao, c_modalidade.situacao) AS situacao,
        COALESCE(c1.justificativa_inativo, c2.justificativa_inativo, c3.justificativa_inativo, f.justificativa_inativo, c_modalidade.justificativa_inativo) AS justificativa_inativo,
        COALESCE(c1.categoria, c2.categoria, c3.categoria, f.categoria, c_modalidade.categoria) AS categoria,
        COALESCE(c1.subcategoria, c2.subcategoria, c3.subcategoria, f.subcategoria, c_modalidade.subcategoria) AS subcategoria,
        COALESCE(c1.unidades_requisitantes, c2.unidades_requisitantes, c3.unidades_requisitantes, f.unidades_requisitantes, c_modalidade.unidades_requisitantes) AS unidades_requisitantes,
        COALESCE(c1.processo, c2.processo, c3.processo, f.processo, c_modalidade.processo) AS processo,
        COALESCE(c1.objeto, c2.objeto, c3.objeto, f.objeto, c_modalidade.objeto) AS objeto,
        COALESCE(c1.amparo_legal, c2.amparo_legal, c3.amparo_legal, f.amparo_legal, c_modalidade.amparo_legal) AS amparo_legal,
        COALESCE(c1.informacao_complementar, c2.informacao_complementar, c3.informacao_complementar, f.informacao_complementar, c_modalidade.informacao_complementar) AS informacao_complementar,
        COALESCE(c1.codigo_modalidade, c2.codigo_modalidade, c3.codigo_modalidade, f.codigo_modalidade, c_modalidade.codigo_modalidade) AS codigo_modalidade,
        COALESCE(c1.modalidade, c2.modalidade, c3.modalidade, f.modalidade, c_modalidade.modalidade) AS modalidade,
        COALESCE(c1.unidade_compra, c2.unidade_compra, c3.unidade_compra, f.unidade_compra, c_modalidade.unidade_compra) AS unidade_compra,
        COALESCE(c1.licitacao_numero, c2.licitacao_numero, c3.licitacao_numero, f.licitacao_numero, c_modalidade.licitacao_numero) AS licitacao_numero,
        COALESCE(c1.sistema_origem_licitacao, c2.sistema_origem_licitacao, c3.sistema_origem_licitacao, f.sistema_origem_licitacao, c_modalidade.sistema_origem_licitacao) AS sistema_origem_licitacao,
        COALESCE(c1.data_assinatura, c2.data_assinatura, c3.data_assinatura, f.data_assinatura, c_modalidade.data_assinatura) AS data_assinatura,
        COALESCE(c1.data_publicacao, c2.data_publicacao, c3.data_publicacao, f.data_publicacao, c_modalidade.data_publicacao) AS data_publicacao,
        COALESCE(c1.data_proposta_comercial, c2.data_proposta_comercial, c3.data_proposta_comercial, f.data_proposta_comercial, c_modalidade.data_proposta_comercial) AS data_proposta_comercial,
        COALESCE(c1.vigencia_inicio, c2.vigencia_inicio, c3.vigencia_inicio, f.vigencia_inicio, c_modalidade.vigencia_inicio) AS vigencia_inicio,
        COALESCE(c1.vigencia_fim, c2.vigencia_fim, c3.vigencia_fim, f.vigencia_fim, c_modalidade.vigencia_fim) AS vigencia_fim,
        COALESCE(c1.valor_inicial, c2.valor_inicial, c3.valor_inicial, f.valor_inicial, c_modalidade.valor_inicial) AS valor_inicial,
        COALESCE(c1.valor_global, c2.valor_global, c3.valor_global, f.valor_global, c_modalidade.valor_global) AS valor_global,
        COALESCE(c1.num_parcelas, c2.num_parcelas, c3.num_parcelas, f.num_parcelas, c_modalidade.num_parcelas) AS num_parcelas,
        COALESCE(c1.valor_parcela, c2.valor_parcela, c3.valor_parcela, f.valor_parcela, c_modalidade.valor_parcela) AS valor_parcela,
        COALESCE(c1.valor_acumulado, c2.valor_acumulado, c3.valor_acumulado, f.valor_acumulado, c_modalidade.valor_acumulado) AS valor_acumulado,
        COALESCE(c1.links_historico, c2.links_historico, c3.links_historico, f.links_historico, c_modalidade.links_historico) AS links_historico,
        COALESCE(c1.links_empenhos, c2.links_empenhos, c3.links_empenhos, f.links_empenhos, c_modalidade.links_empenhos) AS links_empenhos,
        COALESCE(c1.links_cronograma, c2.links_cronograma, c3.links_cronograma, f.links_cronograma, c_modalidade.links_cronograma) AS links_cronograma,
        COALESCE(c1.links_garantias, c2.links_garantias, c3.links_garantias, f.links_garantias, c_modalidade.links_garantias) AS links_garantias,
        COALESCE(c1.links_itens, c2.links_itens, c3.links_itens, f.links_itens, c_modalidade.links_itens) AS links_itens,
        COALESCE(c1.links_prepostos, c2.links_prepostos, c3.links_prepostos, f.links_prepostos, c_modalidade.links_prepostos) AS links_prepostos,
        COALESCE(c1.links_responsaveis, c2.links_responsaveis, c3.links_responsaveis, f.links_responsaveis, c_modalidade.links_responsaveis) AS links_responsaveis,
        COALESCE(c1.links_despesas_acessorias, c2.links_despesas_acessorias, c3.links_despesas_acessorias, f.links_despesas_acessorias, c_modalidade.links_despesas_acessorias) AS links_despesas_acessorias,
        COALESCE(c1.links_faturas, c2.links_faturas, c3.links_faturas, f.links_faturas, c_modalidade.links_faturas) AS links_faturas,
        COALESCE(c1.links_ocorrencias, c2.links_ocorrencias, c3.links_ocorrencias, f.links_ocorrencias, c_modalidade.links_ocorrencias) AS links_ocorrencias,
        COALESCE(c1.links_terceirizados, c2.links_terceirizados, c3.links_terceirizados, f.links_terceirizados, c_modalidade.links_terceirizados) AS links_terceirizados,
        COALESCE(c1.links_arquivos, c2.links_arquivos, c3.links_arquivos, f.links_arquivos, c_modalidade.links_arquivos) AS links_arquivos,
        
        CASE 
            WHEN ec.ne_ccor_favorecido = c1.fornecedor_cnpj_cpf_idgener THEN 'fornecedor_cnpj_cpf_idgener'
            WHEN ec.ne_ccor_favorecido != c1.fornecedor_cnpj_cpf_idgener
                AND REGEXP_REPLACE(ec.ne_num_processo, '[\./-]', '', 'g') = c2.processo THEN 'processo'
            WHEN ec.ne_ccor_favorecido != c1.fornecedor_cnpj_cpf_idgener
                AND REGEXP_REPLACE(ec.ne_num_processo, '[\./-]', '', 'g') != c2.processo
                AND RIGHT(ec.ne_ccor, 12) = c3.numero THEN 'numero'
            WHEN ec.ne_ccor_favorecido != c1.fornecedor_cnpj_cpf_idgener
                AND REGEXP_REPLACE(ec.ne_num_processo, '[\./-]', '', 'g') != c2.processo
                AND RIGHT(ec.ne_ccor, 12) != c3.numero
                AND RIGHT(ec.ne_ccor, 12) = f.numero_empenho THEN 'faturas'
            WHEN ec.ne_ccor_favorecido != c1.fornecedor_cnpj_cpf_idgener
                AND REGEXP_REPLACE(ec.ne_num_processo, '[\./-]', '', 'g') != c2.processo
                AND RIGHT(ec.ne_ccor, 12) != c3.numero
                AND RIGHT(ec.ne_ccor, 12) != f.numero_empenho
                AND (
                    (c_modalidade.codigo_modalidade = 5 
                        AND ec.ne_informacao_complementar LIKE CONCAT('%', c_modalidade.contratante_orgao_unidade_gestora_codigo, TO_CHAR(c_modalidade.codigo_modalidade, 'FM00'), REGEXP_REPLACE(c_modalidade.numero, '[\./-]', '', 'g'), '%'))
                    OR
                    (c_modalidade.codigo_modalidade = 7 
                        AND ec.ne_informacao_complementar LIKE CONCAT('%', c_modalidade.contratante_orgao_unidade_gestora_codigo, TO_CHAR(c_modalidade.codigo_modalidade, 'FM00'), REGEXP_REPLACE(c_modalidade.licitacao_numero, '[\./-]', '', 'g'), '%'))
                )
                THEN 'informacao_complementar'
            ELSE NULL
        END AS origem

    FROM {{ ref('empenhos_tesouro') }} ec
    LEFT JOIN contratos_unicos c1 ON ec.ne_ccor_favorecido = c1.fornecedor_cnpj_cpf_idgener
    LEFT JOIN processos_unicos c2 ON REGEXP_REPLACE(ec.ne_num_processo, '[\./-]', '', 'g') = c2.processo AND c1.id IS NULL
    LEFT JOIN numeros_unicos c3 ON RIGHT(ec.ne_ccor, 12) = c3.numero AND c1.id IS NULL AND c2.id IS NULL
    LEFT JOIN faturas_contratos f ON RIGHT(ec.ne_ccor,12) = f.numero_empenho AND c1.id IS NULL AND c2.id IS NULL AND c3.id IS NULL
    LEFT JOIN public_raw.contratos c_modalidade ON         
        (
            (                
                c_modalidade.codigo_modalidade = '5' 
                AND ec.ne_informacao_complementar like CONCAT('%',c_modalidade.contratante_orgao_unidade_gestora_codigo, TO_CHAR(c_modalidade.codigo_modalidade, 'FM00'), REGEXP_REPLACE(c_modalidade.numero, '[\./-]', '', 'g'), '%')            
            )
            OR             
            (
                c_modalidade.codigo_modalidade = '7'                 
                AND ec.ne_informacao_complementar like CONCAT('%',c_modalidade.contratante_orgao_unidade_gestora_codigo, TO_CHAR(c_modalidade.codigo_modalidade, 'FM00'), REGEXP_REPLACE(c_modalidade.licitacao_numero, '[\./-]', '', 'g'), '%')
            )        
        ) AND c1.id IS NULL AND c2.id IS NULL AND c3.id IS NULL AND f.id IS NULL
)

SELECT * FROM empenhos_contratos