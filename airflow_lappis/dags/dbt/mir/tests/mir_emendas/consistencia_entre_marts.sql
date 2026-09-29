-- Falha se o empenhado de emenda nao fechar entre os tres marts (spec §11):
-- Convenios (origem Emenda) + TEDs (origem Emenda) + Emendas executadas por
-- convenio de outro orgao ou sem instrumento = total do mart de Emendas.
with
    convenios as (
        select coalesce(sum(despesas_empenhadas), 0) as v
        from {{ ref("fato_execucao_orcamentaria") }}
        where origem_recurso = 'Emenda'
    ),

    teds as (
        select coalesce(sum(despesas_empenhadas), 0) as v
        from {{ ref("teds_fato_execucao_orcamentaria") }}
        where origem_recurso = 'Emenda'
    ),

    fora_dos_marts as (
        select coalesce(sum(f.despesas_empenhadas), 0) as v
        from {{ ref("emendas_fato_execucao_orcamentaria") }} as f
        inner join
            {{ ref("emendas_dim_instrumento_executor") }} as i
            on i.sk_instrumento_executor = f.sk_instrumento_executor
        where
            i.tipo_instrumento
            in ('Convênio de outro órgão', 'Execução direta / não identificado')
    ),

    emendas as (
        select coalesce(sum(despesas_empenhadas), 0) as v
        from {{ ref("emendas_fato_execucao_orcamentaria") }}
    )

select c.v as convenios, t.v as teds, o.v as fora_dos_marts, e.v as total_emendas
from convenios as c, teds as t, fora_dos_marts as o, emendas as e
where c.v + t.v + o.v <> e.v
