{{ config(materialized="table") }}

with
    agenda_programa_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            codigo_agenda::text as codigo_agenda,
            programa::text as programa,
            titulo::text as titulo,
            tipo::text as tipo,
            orgao::text as orgao,
            publico_alvo::text as publico_alvo,
            descricao_do_problema::text as descricao_do_problema,
            causa_do_problema::text as causa_do_problema,
            evidencias_do_problema::text as evidencias_do_problema,
            justificativa_para_a_intervencao::text as justificativa_para_a_intervencao,
            evolucao_historica::text as evolucao_historica,
            comparacoes_internacionais::text as comparacoes_internacionais,
            relacao_com_os_ods::text as relacao_com_os_ods,
            agentes_envolvidos::text as agentes_envolvidos,
            articulacao_federativa::text as articulacao_federativa,
            enfoque_transversal::text as enfoque_transversal,
            marco_legal::text as marco_legal,
            planos_nacionais_setoriais_e_regionais::text
            as planos_nacionais_setoriais_e_regionais,
            nome_agenda::text as nome_agenda,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "agenda_programa") }}
    )

select *
from agenda_programa_raw
