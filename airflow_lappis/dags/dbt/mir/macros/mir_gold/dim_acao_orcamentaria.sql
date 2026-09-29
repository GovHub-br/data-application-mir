{#
    Classificacao programatica no grao do PTRES: programa, acao, plano
    orcamentario, funcao e subfuncao (so os codigos de funcao e subfuncao; a
    origem nao traz os nomes).
#}
{% macro dim_acao_orcamentaria() %}
    select {{ surrogate_key(["ptres"]) }} as sk_acao_orcamentaria, a.*
    from
        (
            select distinct
                on (ptres)
                ptres,
                programa_governo as codigo_programa,
                programa_governo_descricao as programa,
                acao_governo as codigo_acao,
                acao_governo_descricao as acao,
                plano_orcamentario_codigo_po as codigo_plano_orcamentario,
                plano_orcamentario_nome as plano_orcamentario,
                plano_orcamentario_codigo_funcao as codigo_funcao,
                plano_orcamentario_codigo_subfuncao as codigo_subfuncao,
                plano_orcamentario_codigo_uo as codigo_uo
            from {{ ref("execucao_ne") }}
            order by ptres, dt_ingest desc
        ) as a

    union all

    select
        -1::bigint,
        '-1',
        null,
        'Não identificado',
        null,
        'Não identificado',
        null,
        'Não identificado',
        null,
        null,
        null
{% endmacro %}
