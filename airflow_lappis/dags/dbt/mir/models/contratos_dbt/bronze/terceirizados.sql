{{ config(materialized="table") }}

with
    terceirizados_raw as (
        select
            nullif(id, '')::integer as id,
            contrato_id::text as contrato_id,
            substring(usuario, '(.+) - ') as cpf,
            substring(usuario, '- (.+)') as nome,
            funcao_id::text as funcao_id,
            descricao_complementar::text as descricao_complementar,
            nullif(jornada, '')::numeric as jornada,
            unidade::text as unidade,
            replace(replace(nullif(salario, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as salario,
            replace(replace(nullif(custo, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as custo,
            escolaridade_id::text as escolaridade_id,
            case
                when data_inicio is not null and data_inicio::text ~ '^\d{4}-\d{2}-\d{2}$'
                then to_date(data_inicio::text, 'YYYY-MM-DD')
            end as data_inicio,
            case
                when data_fim is not null and data_fim::text ~ '^\d{4}-\d{2}-\d{2}$'
                then to_date(data_fim::text, 'YYYY-MM-DD')
            end as data_fim,
            situacao::text as situacao,
            replace(replace(nullif(aux_transporte, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as aux_transporte,
            replace(replace(nullif(vale_alimentacao, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as vale_alimentacao,
            numero_contrato::text as numero_contrato,
            unidade_gestora::text as unidade_gestora,
            unidade_gestora_nome::text as unidade_gestora_nome,
            fornecedor_identificador::text as fornecedor_identificador,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("compras_gov", "terceirizados") }}
    )

select *
from terceirizados_raw