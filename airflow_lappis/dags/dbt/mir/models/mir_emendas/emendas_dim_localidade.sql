{{ config(alias="dim_localidade") }}

-- Localizador do gasto das emendas (NEs e dotacao): regiao e UF, ou NACIONAL.
-- Com NE, os atributos vem da NE. O relatorio poe a regiao ou NACIONAL no
-- lugar da UF quando o gasto nao e de um estado; aqui a UF so fica preenchida
-- quando e um estado (seed uf_regiao), para servir de campo de mapa no BI.
select
    {{ surrogate_key(["l.localizador_gasto"]) }} as sk_localidade,
    l.localizador_gasto,
    l.localizador_descricao,
    l.regiao,
    u.uf,
    case when u.uf is not null then l.uf_nome end as uf_nome
from
    (
        select distinct
            on (localizador_gasto)
            localizador_gasto,
            localizador_descricao,
            regiao,
            uf,
            uf_nome
        from
            (
                select
                    localizador_gasto,
                    localizador_descricao,
                    regiao,
                    uf,
                    uf_nome,
                    1 as origem
                from {{ ref("emenda_ne") }}

                union all

                select
                    localizador_gasto,
                    localizador_descricao,
                    regiao,
                    uf,
                    uf_nome,
                    2 as origem
                from {{ ref("emenda_dotacao") }}
            ) as fontes
        order by localizador_gasto, origem, localizador_descricao
    ) as l
left join {{ ref("uf_regiao") }} as u on u.uf = l.uf

union all

select -1::bigint, '-1', 'Não identificado', null, null, null
