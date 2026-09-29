{#
    Classificacao programatica no grao do PTRES: programa, acao, plano
    orcamentario, funcao e subfuncao (so os codigos de funcao e subfuncao; a
    origem nao traz os nomes). Le os PTRES das NEs e os que so aparecem na
    dotacao das emendas (esses sem plano orcamentario, funcao e subfuncao).
#}
{% macro dim_acao_orcamentaria() %}
    select
        {{ surrogate_key(["ptres"]) }} as sk_acao_orcamentaria,
        ptres,
        codigo_programa,
        programa,
        codigo_acao,
        acao,
        codigo_plano_orcamentario,
        plano_orcamentario,
        codigo_funcao,
        codigo_subfuncao,
        codigo_uo
    from
        (
            select distinct on (ptres) *
            from
                (
                    select
                        ptres,
                        programa_governo as codigo_programa,
                        programa_governo_descricao as programa,
                        acao_governo as codigo_acao,
                        acao_governo_descricao as acao,
                        plano_orcamentario_codigo_po as codigo_plano_orcamentario,
                        plano_orcamentario_nome as plano_orcamentario,
                        plano_orcamentario_codigo_funcao as codigo_funcao,
                        plano_orcamentario_codigo_subfuncao as codigo_subfuncao,
                        plano_orcamentario_codigo_uo as codigo_uo,
                        1 as origem,
                        dt_ingest
                    from {{ ref("execucao_ne") }}

                    union all

                    select
                        ptres,
                        programa_governo,
                        programa_governo_descricao,
                        acao_governo,
                        acao_governo_descricao,
                        null,
                        null,
                        null,
                        null,
                        null,
                        2,
                        null
                    from {{ ref("emenda_dotacao") }}
                ) as fontes
            order by ptres, origem, dt_ingest desc
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
