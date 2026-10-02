{#
    Chaves do gold (spec §4). A chave substituta e um bigint derivado da chave
    natural por md5: estavel entre execucoes, sem sequencia. Dimensao e fato
    calculam a chave com a mesma macro, entao a fato nao precisa de join com a
    dimensao; o teste relationships garante que a chave existe.
#}
{% macro surrogate_key(colunas) -%}
    (
        'x' || substr(
            md5(
                concat_ws(
                    '|'
                    {%- for c in colunas %}, coalesce(({{ c }})::text, ''){% endfor -%}
                )
            ),
            1,
            16
        )
    )::bit(64)::bigint
{%- endmacro %}

{# FK de fato: -1 (Nao identificado) quando a primeira coluna da chave e nula. #}
{% macro fk(colunas) -%}
    case
        when ({{ colunas[0] }}) is null then -1::bigint else {{ surrogate_key(colunas) }}
    end
{%- endmacro %}

{# Chave da dim_tempo: a data como AAAAMMDD; -1 quando a data e nula. #}
{% macro sk_tempo(data) -%}
    coalesce(to_char({{ data }}, 'YYYYMMDD')::bigint, -1::bigint)
{%- endmacro %}
