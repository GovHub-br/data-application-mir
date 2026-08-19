{{ config(materialized='table') }}

with valores_pagos_contratos as (

    select 
        contrato_id as id, 
        coalesce(sum(despesas_empenhadas), 0) as despesas_empenhadas,
        coalesce(sum(despesas_liquidadas), 0) as despesas_liquidadas,
        coalesce(sum(despesas_pagas), 0) as despesas_pagas, 
        max(dt_ingest) as dt_ingest_vpc
    from {{ ref("contratos_empenhos") }}
    where contrato_id is not null
    group by contrato_id

),

contratos_gold as (

    select
        c.*,
        coalesce(vp.despesas_empenhadas, 0) as total_despesas_empenhadas,
        coalesce(vp.despesas_liquidadas, 0) as total_despesas_liquidadas,
        coalesce(vp.despesas_pagas, 0) as total_despesas_pagas,
        vp.dt_ingest_vpc,
        case
            when coalesce(vp.despesas_pagas, 0) = c.valor_global then 'Não'
            else 'Sim'
        end as pendente_baixa
    from {{ ref("contratos") }} as c
    left join valores_pagos_contratos as vp using (id)

)

select
    id as contrato_id,
    numero as numero_contrato,
    situacao as situacao_contrato,
    fornecedor_nome,
    fornecedor_cnpj_cpf_idgener as fornecedor_cnpj_cpf,
    contratante__orgao__nome as orgao_contratante,
    concat(
        contratante__orgao__unidade_gestora__codigo,
        ' - ',
        contratante__orgao__unidade_gestora__nome
    ) as unidade_gestora,
    objeto as objeto_contrato,
    unidades_requisitantes,
    vigencia_inicio,
    vigencia_fim,
    valor_global,
    total_despesas_empenhadas,
    total_despesas_liquidadas,
    total_despesas_pagas,
    pendente_baixa,
    case
        when (vigencia_fim - vigencia_inicio) >= 730 and coalesce(num_parcelas, 0) > 1
        then 'Sim'
        else 'Não'
    end as continuado,
    greatest(dt_ingest, dt_ingest_vpc) as dt_ingest
from contratos_gold