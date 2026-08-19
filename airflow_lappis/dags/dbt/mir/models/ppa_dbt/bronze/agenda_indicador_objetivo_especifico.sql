{{ config(materialized="table") }}

with
    agenda_indicador_objetivo_especifico_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            codigo_agenda::text as codigo_agenda,
            programa::text as programa,
            objetivo::text as objetivo,
            objetivo_especifico::text as objetivo_especifico,
            indicador::text as indicador,
            denominacao::text as denominacao,
            sigla::text as sigla,
            {{ parse_financial_value("indice_de_referencia") }} as indice_de_referencia,
            em_apuracao::text as em_apuracao,
            to_date(nullif(data_de_apuracao, ''), 'DD/MM/YYYY') as data_de_apuracao,
            unidade_de_medida::text as unidade_de_medida,
            descricao::text as descricao,
            periodo_ou_data_a_que_se_refere::text as periodo_ou_data_a_que_se_refere,
            data_de_divulgacao_disponibilizacao::text
            as data_de_divulgacao_disponibilizacao,
            periodicidade::text as periodicidade,
            polaridade::text as polaridade,
            formula_de_calculo::text as formula_de_calculo,
            variaveis_de_calculo::text as variaveis_de_calculo,
            fonte_de_dados_das_variaveis_de_calculo::text
            as fonte_de_dados_das_variaveis_de_calculo,
            forma_de_disponibilizacao::text as forma_de_disponibilizacao,
            procedimento_de_calculo::text as procedimento_de_calculo,
            limitacoes::text as limitacoes,
            notas_explicativas::text as notas_explicativas,
            nome_agenda::text as nome_agenda,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "agenda_indicador_objetivo_especifico") }}
    )

select *
from agenda_indicador_objetivo_especifico_raw
