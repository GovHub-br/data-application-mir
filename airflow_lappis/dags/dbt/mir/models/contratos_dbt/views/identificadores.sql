{{ config(materialized='view') }}

with

ne_empenhos as (

    select
        contrato_id,
        nota_empenho as ne
    from {{ ref('empenhos') }}
    where nota_empenho is not null

),

ne_faturas as (

    select
        f.contrato_id,
        item ->> 'numero_empenho' as ne
    from {{ ref('faturas') }} f
    cross join lateral jsonb_array_elements(
        replace(f.dados_empenho, '''', '"')::jsonb
    ) as item
    where f.dados_empenho is not null
      and f.dados_empenho <> ''
      and f.dados_empenho <> '[]'
      and f.dados_empenho <> 'None'

),

ne_unificadas as (

    select contrato_id, ne from ne_empenhos
    union
    select contrato_id, ne from ne_faturas

),

final as (

    select

        coalesce(nu.contrato_id, c.id) as contrato_id,

        c.categoria,

        regexp_replace(c.processo, '[^0-9]', '', 'g') as processo,

        regexp_replace(c.fornecedor_cnpj_cpf_idgener, '[^0-9]', '', 'g') as cnpj_cpf,

        concat_ws(
            ' - ',
            c.contratante__orgao__unidade_gestora__codigo,
            c.modalidade,
            coalesce(c.licitacao_numero, c.numero)
        ) as info_complementar,

        case
            when
                length(
                    regexp_replace(
                        coalesce(nu.ne, c.numero), '[^0-9A-Za-z]', '', 'g'
                    )
                ) = 12
                then
                    upper(
                        regexp_replace(
                            coalesce(nu.ne, c.numero), '[^0-9A-Za-z]', '', 'g'
                        )
                    )
            else null
        end as ne

    from ne_unificadas nu
    full join {{ ref('contratos') }} c
        on nu.contrato_id = c.id

)

select distinct * from final