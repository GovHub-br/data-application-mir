{{
    config(
        materialized="incremental",
        unique_key="id_hash",
        incremental_strategy="merge",
    )
}}


with
    ppa_tesouro_raw as (
        select
            programa_governo::text as programa_governo,
            programa_governo_descricao::text as programa_governo_descricao,
            acao_governo::text as acao_governo,
            acao_governo_descricao::text as acao_governo_descricao,
            emissao_mes::text as emissao_mes,
            emissao_dia::text as emissao_dia,
            ne_ccor::text as ne_ccor,
            ug_responsavel_codigo::text as ug_responsavel_codigo,
            ug_responsavel_nome::text as ug_responsavel_nome,
            regexp_replace(ne_num_processo, '[./-]', '', 'g') as ne_num_processo,
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
            plano_orcamentario_codigo_uo::text as plano_orcamentario_codigo_uo,
            plano_orcamentario_codigo_funcao::text as plano_orcamentario_codigo_funcao,
            plano_orcamentario_codigo_subfuncao::text as plano_orcamentario_codigo_subfuncao,
            plano_orcamentario_codigo_programa::text as plano_orcamentario_codigo_programa,
            plano_orcamentario_codigo_acao::text as plano_orcamentario_codigo_acao,
            plano_orcamentario_codigo_po::text as plano_orcamentario_codigo_po,
            plano_orcamentario_nome::text as plano_orcamentario_nome,
            resultado_eof_codigo::integer as resultado_eof_codigo,
            resultado_eof_nome::text as resultado_eof_nome,
            grupo_despesa::integer as grupo_despesa,
            grupo_despesa_desc::text as grupo_despesa_desc,
            {{ parse_financial_value("dotacao_atualizada") }} as dotacao_atualizada,
            {{ parse_financial_value("despesas_empenhadas") }} as despesas_empenhadas,
            {{ parse_financial_value("despesas_liquidadas") }} as despesas_liquidadas,
            {{ parse_financial_value("despesas_pagas") }} as despesas_pagas,
            {{ parse_financial_value("restos_a_pagar_inscritos") }} as restos_a_pagar_inscritos,
            {{ parse_financial_value("restos_a_pagar_pagos") }} as restos_a_pagar_pagos,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siafi", "ne_tesouro_ppa") }}
        -- Modelo unico de bronze do relatorio "Notas de empenhos por
        -- programa PPA" do Tesouro Gerencial. Reune os dois graos que
        -- vem na tabela raw:
        --   * grao de empenho (ne_ccor <> '-9'): uma linha por movimentacao
        --     contabil de uma NE real, com despesas_*/restos_a_pagar_*
        --     preenchidos;
        --   * grao de dotacao (ne_ccor = '-9'): limite orcamentario
        --     apropriado por classificacao, com dotacao_atualizada
        --     preenchido.
        -- O filtro abaixo garante apenas que o ano seja um inteiro valido
        -- para o cast (empenhos trazem AAAA; dotacao traz o sentinela -9).
        where ne_ccor_ano_emissao ~ '^-?[0-9]+$'
    )

select
    *,
    -- Chave surrogada estavel para o merge incremental. Cobre todas as
    -- colunas de negocio (exclui dt_ingest para tornar a reingestao do
    -- mesmo dado idempotente). Necessaria porque nenhum subconjunto de
    -- colunas identifica sozinho o grao de dotacao (ne_ccor = '-9'): essas
    -- linhas so se distinguem por ptres/plano_orcamentario/dotacao, etc.
    md5(
        concat_ws(
            '|',
            programa_governo,
            acao_governo,
            emissao_mes,
            emissao_dia,
            ne_ccor,
            ug_responsavel_codigo,
            ne_num_processo,
            ne_info_complementar,
            doc_observacao,
            natureza_despesa,
            ne_ccor_favorecido,
            ne_ccor_ano_emissao,
            ptres,
            fonte_recursos_detalhada,
            plano_orcamentario_codigo_uo,
            plano_orcamentario_codigo_funcao,
            plano_orcamentario_codigo_subfuncao,
            plano_orcamentario_codigo_programa,
            plano_orcamentario_codigo_acao,
            plano_orcamentario_codigo_po,
            resultado_eof_codigo,
            grupo_despesa,
            dotacao_atualizada,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            restos_a_pagar_inscritos,
            restos_a_pagar_pagos
        )
    ) as id_hash
from ppa_tesouro_raw
