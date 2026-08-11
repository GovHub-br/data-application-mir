{{ config(materialized="table") }}

with

cronograma_mensal as (

    select
        cast(contrato_id as text) as contrato_id,
        anoref,
        mesref,
        make_date(anoref, mesref, 1) as mes_referencia,
        sum(coalesce(valor, 0)) as valor_cronograma

    from {{ ref('cronograma') }}
    group by 1, 2, 3, 4

),

faturas_pagas_mensal as (

    select
        cast(contrato_id as text) as contrato_id,
        extract(year from emissao)::integer as anoref,
        extract(month from emissao)::integer as mesref,
        date_trunc('month', emissao)::date as mes_referencia,
        sum(coalesce(valor, 0)) as valor_faturas_pagas

    from {{ ref('faturas') }}
    where lower(trim(situacao)) = 'siafi apropriado'
      and emissao is not null
    group by 1, 2, 3, 4

),

faturas_pendentes_mensal as (

    select
        cast(contrato_id as text) as contrato_id,
        extract(year from emissao)::integer as anoref,
        extract(month from emissao)::integer as mesref,
        date_trunc('month', emissao)::date as mes_referencia,
        sum(coalesce(valor, 0)) as valor_faturas_pendentes

    from {{ ref('faturas') }}
    where lower(trim(situacao)) = 'pendente'
      and emissao is not null
    group by 1, 2, 3, 4

),

cronograma_faturas as (

    select
        c.contrato_id,
        c.anoref,
        c.mesref,
        c.mes_referencia,
        coalesce(c.valor_cronograma, 0) as valor_cronograma,
        coalesce(fp.valor_faturas_pagas, 0) as valor_faturas_pagas,
        coalesce(fpe.valor_faturas_pendentes, 0) as valor_faturas_pendentes,
        coalesce(c.valor_cronograma, 0) 
            - coalesce(fp.valor_faturas_pagas, 0) 
            - coalesce(fpe.valor_faturas_pendentes, 0) as saldo_contratual_disponivel

    from cronograma_mensal c
    left join faturas_pagas_mensal fp
        on c.contrato_id = fp.contrato_id
        and c.anoref = fp.anoref
        and c.mesref = fp.mesref
    left join faturas_pendentes_mensal fpe
        on c.contrato_id = fpe.contrato_id
        and c.anoref = fpe.anoref
        and c.mesref = fpe.mesref

),

final as (

    select
        cf.contrato_id,
        cf.anoref,
        cf.mesref,
        cf.mes_referencia,
        cf.valor_cronograma,
        cf.valor_faturas_pagas,
        cf.valor_faturas_pendentes,
        cf.saldo_contratual_disponivel,
        ct.numero as numero_contrato,
        ct.situacao as situacao_contrato,
        ct.fornecedor_nome,
        ct.fornecedor_cnpj_cpf_idgener,
        ct.contratante__orgao__nome as orgao_contratante,
        ct.contratante__orgao__unidade_gestora__nome as unidade_gestora,
        ct.vigencia_inicio,
        ct.vigencia_fim

    from cronograma_faturas cf
    left join {{ ref('contratos') }} ct
        on trim(cf.contrato_id) = trim(ct.id)

)

select * from final