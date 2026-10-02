{#
    Natureza de despesa (6 digitos: categoria, GND, modalidade de aplicacao,
    elemento). A modalidade de aplicacao sai dos digitos 3 e 4. Le as naturezas
    das NEs e as que so aparecem na dotacao das emendas.
#}
{% macro dim_natureza_despesa() %}
    select
        {{ surrogate_key(["natureza_despesa"]) }} as sk_natureza_despesa,
        natureza_despesa,
        natureza_despesa_descricao,
        codigo_gnd,
        gnd,
        substr(natureza_despesa, 3, 2) as codigo_modalidade_aplicacao
    from
        (
            select distinct on (natureza_despesa) *
            from
                (
                    select
                        natureza_despesa,
                        natureza_despesa_descricao,
                        grupo_despesa as codigo_gnd,
                        grupo_despesa_desc as gnd,
                        1 as origem,
                        dt_ingest
                    from {{ ref("execucao_ne") }}

                    union all

                    select
                        natureza_despesa,
                        natureza_despesa_descricao,
                        grupo_despesa,
                        grupo_despesa_descricao,
                        2,
                        null
                    from {{ ref("emenda_dotacao") }}
                ) as fontes
            order by natureza_despesa, origem, dt_ingest desc
        ) as n

    union all

    select -1::bigint, '-1', 'Não identificado', null, 'Não identificado', null
{% endmacro %}
