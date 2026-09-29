{{ config(alias="dim_localidade") }}

-- Localizador do gasto das emendas (NEs e dotacao): regiao e UF, ou NACIONAL.
-- Com NE, os atributos vem da NE.
select
    {{ surrogate_key(["localizador_gasto"]) }} as sk_localidade,
    localizador_gasto,
    localizador_descricao,
    regiao,
    uf,
    uf_nome
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

union all

select -1::bigint, '-1', 'Não identificado', null, null, null
