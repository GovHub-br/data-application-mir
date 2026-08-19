{{ config(materialized="table") }}

with
    entrega_raw as (
        select
            nullif(exercicio, '')::integer as exercicio,
            programa::text as programa,
            objetivo::text as objetivo,
            objetivo_especifico::text as objetivo_especifico,
            entrega::text as entrega,
            enunciado::text as enunciado,
            descricao::text as descricao,
            orgao::text as orgao,
            unidade_responsavel::text as unidade_responsavel,
            projeto_de_investimento::text as projeto_de_investimento,
            to_date(nullif(data_de_inicio, ''), 'DD/MM/YYYY') as data_de_inicio,
            data_de_termino::text as data_de_termino,
            {{ parse_financial_value("valor_total") }} as valor_total,
            {{ parse_financial_value("execucao_fisica_acumulada") }}
            as execucao_fisica_acumulada,
            {{ parse_financial_value("meta_da_execucao_fisica") }}
            as meta_da_execucao_fisica,
            pac::text as pac,
            identificador_cadastro_novo_pac_governa::text
            as identificador_cadastro_novo_pac_governa,
            concluida::text as concluida,
            nullif(ano_ppa, '')::integer as ano_ppa,
            id_hash::text as id_hash,
            nullif(dt_ingest, '')::timestamp as dt_ingest
        from {{ source("ppa", "entrega") }}
    )

select *
from entrega_raw
