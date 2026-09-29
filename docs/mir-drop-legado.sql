-- Remove do banco as tabelas da silver e do gold antigos do MIR, substituidos
-- pelos marts mir_convenios, mir_teds e mir_emendas (remodelagem fato-dimensao,
-- etapa 5). Os modelos ja sairam do dbt: essas tabelas estao paradas desde o
-- deploy. Rodar so depois de migrar os paineis do Power BI
-- (docs/mir-guia-migracao-power-bi.md).
--
-- Sem cascade: se um painel ou view ainda depender de uma tabela, o drop falha
-- e a transacao inteira volta atras. O planos_partidos (emendas PIX) fica.
begin;

drop view siafi_dbt.num_transf_n_plano_acao;

drop table emendas.emendas_execucao_por_ug;
drop table emendas.emendas_instrumentos_execucao;
drop table emendas.emendas_orcamento_execucao;
drop table emendas.emendas_partidos;
drop table emendas.instrumentos_emendas;
drop table emendas.resumo_emendas_orcamento_execucao;

drop table siafi_dbt.empenhos_por_plano_acao;
drop table siafi_dbt.nc_plano_acao;
drop table siafi_dbt.nc_unificado;
drop table siafi_dbt.pf_unificado;
drop table siafi_dbt.pf_unificado_planos_acao;
drop table siafi_dbt.ted_empenhos_plano_acao;
drop table siafi_dbt.ted_resumo_orcamentario;

drop table siconv_dbt.convenio_cronograma_desembolso;
drop table siconv_dbt.convenio_desbloqueio;
drop table siconv_dbt.convenio_desembolso;
drop table siconv_dbt.convenio_empenho;
drop table siconv_dbt.convenio_historico_situacao;
drop table siconv_dbt.convenio_ingresso_contrapartida;
drop table siconv_dbt.convenio_licitacao;
drop table siconv_dbt.convenio_meta_crono_fisico;
drop table siconv_dbt.convenio_pagamento;
drop table siconv_dbt.convenio_pagamento_tributo;
drop table siconv_dbt.convenio_proposta;
drop table siconv_dbt.convenio_proposta_pagamento;
drop table siconv_dbt.convenio_prorroga_oficio;
drop table siconv_dbt.convenio_solicitacao_alteracao;
drop table siconv_dbt.convenio_solicitacao_rendimento;
drop table siconv_dbt.convenio_termo_aditivo;
drop table siconv_dbt.convenios_consolidados;
drop table siconv_dbt.emendas_convenio;
drop table siconv_dbt.meta_cronograma_desembolso;
drop table siconv_dbt.numero_transferencia;
drop table siconv_dbt.proposta_convenio;
drop table siconv_dbt.proposta_cronograma_desembolso;
drop table siconv_dbt.proposta_historico_situacao;
drop table siconv_dbt.proposta_meta_crono_fisico;
drop table siconv_dbt.resumo_convenios;
drop table siconv_dbt.resumo_termos_fomento;
drop table siconv_dbt.termo_fomento_consolidado;

commit;
