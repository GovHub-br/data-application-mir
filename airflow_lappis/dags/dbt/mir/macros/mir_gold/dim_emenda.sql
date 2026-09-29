{#
    Emenda parlamentar. O codigo tem 12 digitos: ano (4) + autor (4) + numero
    (4), ex.: 202443740013 = emenda 13 de 2024.
#}
{% macro dim_emenda() %}
    select
        {{ surrogate_key(["codigo_emenda"]) }} as sk_emenda,
        codigo_emenda,
        left(codigo_emenda, 4)::integer as ano,
        right(codigo_emenda, 4)::integer as numero,
        emenda_descricao,
        autor_nome
    from
        (
            select distinct on (codigo_emenda) codigo_emenda, emenda_descricao, autor_nome
            from {{ ref("emenda_ne") }}
            order by codigo_emenda, ne_ccor
        ) as e

    union all

    select -1::bigint, '-1', null, null, 'Não identificado', 'Não identificado'
{% endmacro %}
