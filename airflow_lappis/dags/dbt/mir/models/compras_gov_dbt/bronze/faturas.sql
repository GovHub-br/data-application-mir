{{ config(materialized="table") }}

with
    faturas_raw as (
        select
            nullif(id, '')::integer as id,
            contrato_id::text as contrato_id,
            tipolistafatura_id::text as tipolistafatura_id,
            tipo_instrumento_cobranca::text as tipo_instrumento_cobranca,
            justificativafatura_id::text as justificativafatura_id,
            sfadrao_id::text as sfadrao_id,
            numero::text as numero,
            numero_serie::text as numero_serie,
            fornecedor_contrato::text as fornecedor_contrato,
            fornecedor_ic::text as fornecedor_ic,
            contratante::text as contratante,
            case
                when emissao is not null and emissao::text ~ '^\d{4}-\d{2}-\d{2}$'
                then emissao::date
            end as emissao,
            case
                when prazo is not null and prazo::text ~ '^\d{4}-\d{2}-\d{2}$'
                then prazo::date
            end as prazo,
            case
                when vencimento is not null and vencimento::text ~ '^\d{4}-\d{2}-\d{2}$'
                then vencimento::date
            end as vencimento,
            replace(replace(nullif(valor, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as valor,
            replace(replace(nullif(juros, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as juros,
            replace(replace(nullif(multa, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as multa,
            replace(replace(nullif(glosa, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as glosa,
            replace(replace(nullif(valorliquido, ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as valorliquido,
            base_calculo_inss::text as base_calculo_inss,
            aliquota_inss::text as aliquota_inss,
            optante_cprb::text as optante_cprb,
            optante_simples::text as optante_simples,
            valor_inss::text as valor_inss,
            case
                when
                    data_liquidacao is not null
                    and data_liquidacao::text ~ '^\d{4}-\d{2}-\d{2}$'
                then to_date(data_liquidacao::text, 'YYYY-MM-DD')
            end as data_liquidacao,
            nota_cancelada::text as nota_cancelada,
            processo::text as processo,
            case
                when protocolo is not null and protocolo::text ~ '^\d{4}-\d{2}-\d{2}$'
                then protocolo::date
            end as protocolo,
            case
                when ateste is not null and ateste::text ~ '^\d{4}-\d{2}-\d{2}$'
                then ateste::date
            end as ateste,
            repactuacao::text as repactuacao,
            infcomplementar::text as infcomplementar,
            nullif(mesref, '')::integer as mesref,
            nullif(anoref, '')::integer as anoref,
            situacao::text as situacao,
            chave_nfe::text as chave_nfe,
            dados_referencia::text as dados_referencia,
            dados_item_faturado::text as dados_item_faturado,
            dados_empenho::text as dados_empenho,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("compras_gov", "faturas") }}
    )

select *
from faturas_raw