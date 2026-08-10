{{ config(materialized="table") }}

with
    contratos as (
        select
            trim(cast(id as text)) as contrato_id_key,
            fornecedor_cnpj_cpf_idgener,
            fornecedor_tipo,
            fornecedor_nome,
            processo as processo_contrato,
            numero as numero_contrato,
            objeto as objeto_contrato,
            unidades_requisitantes,
            dt_ingest as dt_ingest_contratos
        from {{ ref("contratos") }}
    ),

    faturas_base as (
        select * 
        from {{ ref("faturas") }}
    )

select
    f.*,
    c.numero_contrato,
    c.processo_contrato as contrato_processo,
    c.fornecedor_cnpj_cpf_idgener,
    c.fornecedor_tipo,
    c.fornecedor_nome,
    c.objeto_contrato,
    c.unidades_requisitantes
from faturas_base f
left join contratos c 
    on trim(cast(f.contrato_id as text)) = c.contrato_id_key