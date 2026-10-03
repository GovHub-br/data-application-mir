{{ config(materialized="table") }}

{#
  Planos de ação do portal do sistema TED (ted.transferegov.sistema.gov.br),
  com os mesmos nomes e tipos de planos_acao_ted (API de dados abertos) e as
  colunas que só o portal tem. A ingestão grava os nulos da API como o texto
  'NaN' (pandas), então toda coluna passa por texto_sem_nan().
#}
with
    planos_acao_portal_raw as (
        select
            {{ texto_sem_nan("id_plano_acao") }}::integer as id_plano_acao,
            {{ texto_sem_nan("id_programa") }}::integer as id_programa,
            {{ texto_sem_nan("sigla_unidade_descentralizada") }}
            as sigla_unidade_descentralizada,
            {{ texto_sem_nan("unidade_descentralizada") }} as unidade_descentralizada,
            {{ texto_sem_nan("sigla_unidade_responsavel_execucao") }}
            as sigla_unidade_responsavel_execucao,
            {{ texto_sem_nan("unidade_responsavel_execucao") }}
            as unidade_responsavel_execucao,
            {{ texto_sem_nan("vl_total_plano_acao") }}::numeric(
                15, 2
            ) as vl_total_plano_acao,
            {{ texto_sem_nan("dt_inicio_vigencia") }}::date as dt_inicio_vigencia,
            {{ texto_sem_nan("dt_fim_vigencia") }}::date as dt_fim_vigencia,
            {{ texto_sem_nan("tx_objeto_plano_acao") }} as tx_objeto_plano_acao,
            {{ texto_sem_nan("tx_justificativa_plano_acao") }}
            as tx_justificativa_plano_acao,
            {{ texto_sem_nan("in_forma_execucao_direta") }}::boolean
            as in_forma_execucao_direta,
            {{ texto_sem_nan("in_forma_execucao_particulares") }}::boolean
            as in_forma_execucao_particulares,
            {{ texto_sem_nan("in_forma_execucao_descentralizada") }}::boolean
            as in_forma_execucao_descentralizada,
            {{ texto_sem_nan("tx_situacao_plano_acao") }} as tx_situacao_plano_acao,
            {{ texto_sem_nan("aa_ano_plano_acao") }}::integer as aa_ano_plano_acao,
            {{ texto_sem_nan("vl_beneficiario_especifico") }}::numeric(
                15, 2
            ) as vl_beneficiario_especifico,
            {{ texto_sem_nan("vl_chamamento_publico") }}::numeric(
                15, 2
            ) as vl_chamamento_publico,
            {{ texto_sem_nan("sq_instrumento") }} as sq_instrumento,
            {{ texto_sem_nan("aa_instrumento") }}::integer as aa_instrumento,
            -- Só no portal
            {{ texto_sem_nan("codigo_plano_acao") }} as codigo_plano_acao,
            {{ texto_sem_nan("versao_plano_acao") }}::integer as versao_plano_acao,
            {{ texto_sem_nan("cd_ug_unidade_descentralizada") }}
            as cd_ug_unidade_descentralizada,
            {{ texto_sem_nan("cd_ug_unidade_responsavel_execucao") }}
            as cd_ug_unidade_responsavel_execucao,
            {{ texto_sem_nan("id_unidade_descentralizadora") }}
            as id_unidade_descentralizadora,
            {{ texto_sem_nan("sigla_unidade_descentralizadora") }}
            as sigla_unidade_descentralizadora,
            {{ texto_sem_nan("sigla_unidade_responsavel_acompanhamento") }}
            as sigla_unidade_responsavel_acompanhamento,
            {{ texto_sem_nan("unidade_responsavel_acompanhamento") }}
            as unidade_responsavel_acompanhamento,
            {{ texto_sem_nan("in_termo_execucao_assinado") }}::boolean
            as in_termo_execucao_assinado,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("transfere_gov", "planos_acao_portal") }}
    )

select *
from planos_acao_portal_raw
