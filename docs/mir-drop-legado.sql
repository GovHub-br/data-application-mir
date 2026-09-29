-- Remove do banco as tabelas da silver e do gold antigos do MIR, substituidos
-- pelos marts mir_convenios, mir_teds e mir_emendas (remodelagem fato-dimensao,
-- etapa 5). Os modelos ja sairam do dbt: essas tabelas estao paradas desde o
-- deploy. Rodar so depois de migrar os paineis do Power BI
-- (docs/mir-guia-migracao-power-bi.md).
--
-- ATENCAO: paineis do Power BI (importacao ou DirectQuery) nao registram
-- dependencia no Postgres e NAO impedem o drop; um painel que ainda leia uma
-- dessas tabelas quebra. Confirme a migracao de todos os paineis antes.
--
-- Sem cascade: se uma view ou outro objeto do banco ainda depender de uma
-- tabela, o drop falha e a transacao inteira volta atras. Objetos que ja nao
-- existirem sao pulados (if exists). O planos_partidos (emendas PIX) fica.
begin;

drop view if exists siafi_dbt.num_transf_n_plano_acao;

drop table if exists emendas.emendas_execucao_por_ug;
drop table if exists emendas.emendas_instrumentos_execucao;
drop table if exists emendas.emendas_orcamento_execucao;
drop table if exists emendas.emendas_partidos;
drop table if exists emendas.instrumentos_emendas;
drop table if exists emendas.resumo_emendas_orcamento_execucao;

drop table if exists siafi_dbt.empenhos_por_plano_acao;
drop table if exists siafi_dbt.nc_plano_acao;
drop table if exists siafi_dbt.nc_unificado;
drop table if exists siafi_dbt.pf_unificado;
drop table if exists siafi_dbt.pf_unificado_planos_acao;
drop table if exists siafi_dbt.ted_empenhos_plano_acao;
drop table if exists siafi_dbt.ted_resumo_orcamentario;

drop table if exists siconv_dbt.convenio_cronograma_desembolso;
drop table if exists siconv_dbt.convenio_desbloqueio;
drop table if exists siconv_dbt.convenio_desembolso;
drop table if exists siconv_dbt.convenio_empenho;
drop table if exists siconv_dbt.convenio_historico_situacao;
drop table if exists siconv_dbt.convenio_ingresso_contrapartida;
drop table if exists siconv_dbt.convenio_licitacao;
drop table if exists siconv_dbt.convenio_meta_crono_fisico;
drop table if exists siconv_dbt.convenio_pagamento;
drop table if exists siconv_dbt.convenio_pagamento_tributo;
drop table if exists siconv_dbt.convenio_proposta;
drop table if exists siconv_dbt.convenio_proposta_pagamento;
drop table if exists siconv_dbt.convenio_prorroga_oficio;
drop table if exists siconv_dbt.convenio_solicitacao_alteracao;
drop table if exists siconv_dbt.convenio_solicitacao_rendimento;
drop table if exists siconv_dbt.convenio_termo_aditivo;
drop table if exists siconv_dbt.convenios_consolidados;
drop table if exists siconv_dbt.emendas_convenio;
drop table if exists siconv_dbt.meta_cronograma_desembolso;
drop table if exists siconv_dbt.numero_transferencia;
drop table if exists siconv_dbt.proposta_convenio;
drop table if exists siconv_dbt.proposta_cronograma_desembolso;
drop table if exists siconv_dbt.proposta_historico_situacao;
drop table if exists siconv_dbt.proposta_meta_crono_fisico;
drop table if exists siconv_dbt.resumo_convenios;
drop table if exists siconv_dbt.resumo_termos_fomento;
drop table if exists siconv_dbt.termo_fomento_consolidado;

commit;
