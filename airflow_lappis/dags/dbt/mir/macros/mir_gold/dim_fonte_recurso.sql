{# Fonte de recursos detalhada das NEs do nucleo. #}
{% macro dim_fonte_recurso() %}
    select {{ surrogate_key(["codigo_fonte"]) }} as sk_fonte_recurso, f.*
    from
        (
            select distinct
                on (fonte_recursos_detalhada)
                fonte_recursos_detalhada as codigo_fonte,
                fonte_recursos_detalhada_descricao as fonte
            from {{ ref("execucao_ne") }}
            order by fonte_recursos_detalhada, dt_ingest desc
        ) as f

    union all

    select -1::bigint, '-1', 'Não identificado'
{% endmacro %}
