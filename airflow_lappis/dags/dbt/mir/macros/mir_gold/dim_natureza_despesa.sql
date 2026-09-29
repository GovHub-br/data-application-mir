{#
    Natureza de despesa (6 digitos: categoria, GND, modalidade de aplicacao,
    elemento). A modalidade de aplicacao sai dos digitos 3 e 4.
#}
{% macro dim_natureza_despesa() %}
    select {{ surrogate_key(["natureza_despesa"]) }} as sk_natureza_despesa, n.*
    from
        (
            select distinct
                on (natureza_despesa)
                natureza_despesa,
                natureza_despesa_descricao,
                grupo_despesa as codigo_gnd,
                grupo_despesa_desc as gnd,
                substr(natureza_despesa, 3, 2) as codigo_modalidade_aplicacao
            from {{ ref("execucao_ne") }}
            order by natureza_despesa, dt_ingest desc
        ) as n

    union all

    select -1::bigint, '-1', 'Não identificado', null, 'Não identificado', null
{% endmacro %}
