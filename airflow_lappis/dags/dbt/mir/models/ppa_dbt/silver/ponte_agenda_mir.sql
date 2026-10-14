{{ config(materialized="table") }}

-- Tabela ponte (N:M) entre os itens do PPA do MIR e as agendas que os marcam.
-- Só chaves: as tabelas agenda_*_filtrado_mir repetem os valores e metas do item
-- em cada agenda (marcação, não rateio), então somar sobre elas multiplica os
-- totais. Os valores devem ser somados nas tabelas base (entrega, meta_entrega...)
-- e esta ponte serve apenas para filtrar por agenda.
-- Grão: uma linha por ano_ppa x nivel x item x codigo_agenda. Nas medidas
-- institucionais o `enunciado` entra na chave porque em 2024 o código da medida
-- vem vazio na fonte e só o enunciado distingue uma medida da outra.
{% set niveis = [
    ("programa", "agenda_programa_filtrado_mir", []),
    ("objetivo_geral", "agenda_objetivo_geral_filtrado_mir", ["objetivo"]),
    (
        "objetivo_especifico",
        "agenda_objetivo_especifico_filtrado_mir",
        ["objetivo", "objetivo_especifico"],
    ),
    (
        "entrega",
        "agenda_entrega_filtrado_mir",
        ["objetivo", "objetivo_especifico", "entrega"],
    ),
    (
        "indicador_objetivo_especifico",
        "agenda_indicador_objetivo_especifico_filtrado_mir",
        ["objetivo", "objetivo_especifico", "indicador"],
    ),
    (
        "indicador_entrega",
        "agenda_indicador_entrega_filtrado_mir",
        ["objetivo", "objetivo_especifico", "entrega", "indicador"],
    ),
    (
        "meta_objetivo_especifico",
        "agenda_meta_objetivo_especifico_filtrado_mir",
        ["objetivo", "objetivo_especifico", "indicador", "meta_do_objetivo_especifico"],
    ),
    (
        "meta_entrega",
        "agenda_meta_entrega_filtrado_mir",
        ["objetivo", "objetivo_especifico", "entrega", "indicador", "meta_da_entrega"],
    ),
    (
        "regionalizacao_meta_objetivo_especifico",
        "agenda_regionalizacao_meta_objetivo_especifico_filtrado_mir",
        [
            "objetivo",
            "objetivo_especifico",
            "indicador",
            "meta_do_objetivo_especifico",
            "regiao",
        ],
    ),
    (
        "regionalizacao_meta_entrega",
        "agenda_regionalizacao_meta_entrega_filtrado_mir",
        [
            "objetivo",
            "objetivo_especifico",
            "entrega",
            "indicador",
            "meta_da_entrega",
            "regiao",
        ],
    ),
    (
        "desagregacao_meta_objetivo_especifico",
        "agenda_desagregacao_meta_objetivo_especifico_filtrado_mir",
        [
            "objetivo",
            "objetivo_especifico",
            "indicador",
            "meta_do_objetivo_especifico",
            "publico",
        ],
    ),
    (
        "desagregacao_meta_entrega",
        "agenda_desagregacao_meta_entrega_filtrado_mir",
        [
            "objetivo",
            "objetivo_especifico",
            "entrega",
            "indicador",
            "meta_da_entrega",
            "publico",
        ],
    ),
    (
        "medida_institucional_objetivo_especifico",
        "agenda_medida_institucional_objetivo_especifico_filtrado_mir",
        [
            "objetivo",
            "objetivo_especifico",
            "medida_institucional_normativa",
            "enunciado",
        ],
    ),
    (
        "medida_institucional_programa",
        "agenda_medida_institucional_programa_filtrado_mir",
        ["medida_institucional_normativa", "enunciado"],
    ),
] %}

{% set colunas_item = [
    "objetivo",
    "objetivo_especifico",
    "entrega",
    "indicador",
    "meta_do_objetivo_especifico",
    "meta_da_entrega",
    "regiao",
    "publico",
    "medida_institucional_normativa",
    "enunciado",
] %}

with
    ponte as (
        {% for nivel, tabela, colunas in niveis %}
            select distinct
                ano_ppa,
                '{{ nivel }}'::text as nivel,
                programa,
                {% for coluna in colunas_item %}
                    {% if coluna in colunas %} {{ coluna }}
                    {% else %} null::text
                    {% endif %} as {{ coluna }},
                {% endfor %}
                codigo_agenda
            from {{ ref(tabela) }}
            {% if not loop.last %}
                union all
            {% endif %}
        {% endfor %}
    )

select
    ponte.*,
    agenda.chave_agenda,
    agenda.nome_agenda,
    agenda.grupo_agenda,
    agenda.nome_agenda_mae
from ponte
left join
    {{ ref("agenda_filtrado_mir") }} as agenda
    on agenda.codigo = ponte.codigo_agenda
    and agenda.ano_ppa = ponte.ano_ppa
