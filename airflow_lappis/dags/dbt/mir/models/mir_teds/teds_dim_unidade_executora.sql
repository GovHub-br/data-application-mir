{{ config(alias="dim_unidade_executora") }}

-- Unidades que executam os TEDs (UG do lado que nao e o MIR nas NCs e PFs).
select
    {{ surrogate_key(["ug_executora_codigo"]) }} as sk_unidade_executora,
    ug_executora_codigo,
    ug_executora_nome
from {{ ref("ted_unidade_executora") }}

union all

select -1::bigint, '-1', 'Não identificado'
