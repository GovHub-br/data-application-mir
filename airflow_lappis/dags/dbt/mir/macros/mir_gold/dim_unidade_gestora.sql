{# Unidade gestora responsavel das NEs do nucleo. #}
{% macro dim_unidade_gestora() %}
    select {{ surrogate_key(["codigo_ug"]) }} as sk_unidade_gestora, u.*
    from
        (
            select distinct
                on (ug_responsavel_codigo)
                ug_responsavel_codigo as codigo_ug,
                ug_responsavel_nome as nome_ug
            from {{ ref("execucao_ne") }}
            order by ug_responsavel_codigo, dt_ingest desc
        ) as u

    union all

    select -1::bigint, '-1', 'Não identificado'
{% endmacro %}
