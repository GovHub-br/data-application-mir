{#
    Fonte de recursos detalhada das NEs e da dotacao das emendas.
#}
{% macro dim_fonte_recurso() %}
    select {{ surrogate_key(["codigo_fonte"]) }} as sk_fonte_recurso, codigo_fonte, fonte
    from
        (
            select distinct on (codigo_fonte) *
            from
                (
                    select
                        fonte_recursos_detalhada as codigo_fonte,
                        fonte_recursos_detalhada_descricao as fonte,
                        1 as origem,
                        dt_ingest
                    from {{ ref("execucao_ne") }}

                    union all

                    select
                        fonte_recursos_detalhada,
                        fonte_recursos_detalhada_descricao,
                        2,
                        null
                    from {{ ref("emenda_dotacao") }}
                ) as fontes
            order by codigo_fonte, origem, dt_ingest desc
        ) as f

    union all

    select -1::bigint, '-1', 'Não identificado'
{% endmacro %}
