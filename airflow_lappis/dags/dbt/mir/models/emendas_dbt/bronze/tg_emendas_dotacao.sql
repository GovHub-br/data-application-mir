{{ config(materialized="table") }}

with
	tg_emendas_dotacao_raw as (
		select
			-- Grao de dotacao orcamentaria: uma linha por classificacao
			-- (programa/acao/localizador/natureza/modalidade/fonte/ptres),
			-- sem empenho associado (ne_ccor = '-9' na tabela raw).
			case
				when emissao_mes ~ '^[A-Z]{3}/[0-9]{4}$'
				then {{ target.schema }}.parse_date(emissao_mes)
			end as emissao_mes,
			case
				when emissao_dia ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
				then to_date(emissao_dia, 'DD/MM/YYYY')
			end as emissao_dia,
			programa_governo::integer as programa_governo,
			programa_governo_descricao::text as programa_governo_descricao,
			acao_governo::text as acao_governo,
			acao_governo_descricao::text as acao_governo_descricao,
			autor_emendas_orcamento::text as autor_emendas_orcamento,
			autor_emendas_orcamento_descricao::text as autor_emendas_orcamento_descricao,
			initcap(
				trim(
					regexp_replace(
						split_part(autor_emendas_orcamento_descricao, '/', 1),
						'\s+',
						' ',
						'g'
					)
				)
			) as autor_emendas_orcamento_nome,
			localizador_gasto::text as localizador_gasto,
			localizador_gasto_descricao::text as localizador_gasto_descricao,
			regiao_pt::text as regiao_pt,
			case
    			when uf_pt = '-8' then regiao_pt
    			else uf_pt
			end as uf_pt,
			case
    			when uf_pt_descricao = 'SEM INFORMACAO' then regiao_pt
    			else uf_pt_descricao
			end::text as uf_pt_descricao,
			municipio_pt::text as municipio_pt,
			doc_observacao::text as doc_observacao,
			grupo_despesa::integer as grupo_despesa,
			grupo_despesa_descricao::text as grupo_despesa_descricao,
			natureza_despesa::text as natureza_despesa,
			natureza_despesa_descricao::text as natureza_despesa_descricao,
			modalidade_aplicacao::integer as modalidade_aplicacao,
			modalidade_aplicacao_descricao::text as modalidade_aplicacao_descricao,
			ptres::integer as ptres,
			fonte_recursos_detalhada::text as fonte_recursos_detalhada,
			fonte_recursos_detalhada_descricao::text as fonte_recursos_detalhada_descricao,
			{{ parse_financial_value("dotacao_inicial") }} as dotacao_inicial,
			{{ parse_financial_value("dotacao_atualizada") }} as dotacao_atualizada,
			(dt_ingest || '-03:00')::timestamptz as dt_ingest
		from {{ source("siafi", "ne_tesouro_emendas") }}
		-- Apenas as linhas de dotacao (itens 9/13). O grao de empenho
		-- fica em tg_emendas.
		where ne_ccor = '-9'
	)

select *
from tg_emendas_dotacao_raw
