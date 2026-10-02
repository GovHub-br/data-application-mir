-- Falha se uma agenda vinculada ao MIR em qualquer tabela agenda_*_filtrado_mir
-- não aparecer na dimensão agenda_filtrado_mir. Antes a dimensão só olhava
-- agenda_programa e perdia agendas vinculadas apenas a entregas, metas ou
-- indicadores (ex.: 576 "Igualdade Racial: Enfrentamento à violência...").
{% set vinculos_agenda = [
    "agenda_programa_filtrado_mir",
    "agenda_objetivo_geral_filtrado_mir",
    "agenda_objetivo_especifico_filtrado_mir",
    "agenda_entrega_filtrado_mir",
    "agenda_meta_objetivo_especifico_filtrado_mir",
    "agenda_meta_entrega_filtrado_mir",
    "agenda_indicador_objetivo_especifico_filtrado_mir",
    "agenda_indicador_entrega_filtrado_mir",
    "agenda_desagregacao_meta_objetivo_especifico_filtrado_mir",
    "agenda_desagregacao_meta_entrega_filtrado_mir",
    "agenda_regionalizacao_meta_objetivo_especifico_filtrado_mir",
    "agenda_regionalizacao_meta_entrega_filtrado_mir",
    "agenda_medida_institucional_programa_filtrado_mir",
    "agenda_medida_institucional_objetivo_especifico_filtrado_mir",
] %}

with
    vinculos as (
        {% for vinculo in vinculos_agenda %}
            select '{{ vinculo }}' as tabela, codigo_agenda, ano_ppa
            from {{ ref(vinculo) }}
            {% if not loop.last %}
                union
            {% endif %}
        {% endfor %}
    )

select vinculos.*
from vinculos
left join {{ ref("agenda_filtrado_mir") }} as agenda
    on agenda.codigo = vinculos.codigo_agenda
    and agenda.ano_ppa = vinculos.ano_ppa
where agenda.codigo is null
