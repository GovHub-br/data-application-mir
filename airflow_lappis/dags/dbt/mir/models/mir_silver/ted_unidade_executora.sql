{{ config(materialized="table") }}

-- Unidades que executam os TEDs do MIR: as UGs do lado que nao e o MIR nas NCs
-- e PFs ligadas a TED. O nome vem de onde houver: PF (emitente e favorecido) e
-- favorecido das NCs; quando ha grafias diferentes, fica a maior em ordem
-- alfabetica (escolha deterministica).
with
    codigos as (
        select ug_executora_codigo
        from {{ ref("ted_credito_nc") }}
        union
        select ug_executora_codigo
        from {{ ref("ted_programacao_pf") }}
    ),

    nomes as (
        select ug_emitente as codigo, ug_emitente_descricao as nome
        from {{ ref("pf_tesouro") }}
        union all
        select ug_favorecido, ug_favorecido_descricao
        from {{ ref("pf_tesouro") }}
        union all
        select favorecido_doc, favorecido_doc_descricao
        from {{ ref("nc_tesouro_mir") }}
    )

select c.ug_executora_codigo, max(n.nome) as ug_executora_nome
from codigos as c
left join nomes as n on n.codigo = c.ug_executora_codigo
group by c.ug_executora_codigo
