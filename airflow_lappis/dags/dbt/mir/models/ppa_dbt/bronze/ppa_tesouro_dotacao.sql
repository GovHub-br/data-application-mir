{{ config(materialized="table") }}

with
    ppa_tesouro_dotacao_raw as (
        select
            -- Grao de dotacao orcamentaria: uma linha por classificacao
            -- (programa/acao/natureza/fonte/PTRES/plano orcamentario),
            -- sem empenho associado (ne_ccor = '-9' na tabela raw). Colunas
            -- especificas de NE (ne_ccor, ne_num_processo, favorecido,
            -- ug_responsavel etc. — que vem como '-8'/'SEM INFORMACAO' nesse
            -- grao) e os valores de execucao (despesas_*, restos_a_pagar_*)
            -- nao se aplicam a esse grao e ficam de fora — ver ppa_tesouro.sql.
            programa_governo::text as programa_governo,
            programa_governo_descricao::text as programa_governo_descricao,
            acao_governo::text as acao_governo,
            acao_governo_descricao::text as acao_governo_descricao,
            emissao_mes::text as emissao_mes,
            emissao_dia::text as emissao_dia,
            doc_observacao::text as doc_observacao,
            natureza_despesa::text as natureza_despesa,
            natureza_despesa_descricao::text as natureza_despesa_descricao,
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
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siafi", "ne_tesouro_ppa") }}
        -- Apenas as linhas de dotacao. O grao de empenho fica em
        -- ppa_tesouro.sql.
        where ne_ccor = '-9'
    )

select *
from ppa_tesouro_dotacao_raw
