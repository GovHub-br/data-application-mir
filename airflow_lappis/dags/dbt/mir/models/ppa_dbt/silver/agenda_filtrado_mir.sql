{{ config(materialized="table") }}

-- Dimensão de agendas do PPA usadas pelo MIR. A tabela `agenda` do SIOP é um
-- catálogo de marcadores de vários tipos (agendas transversais, sub-agendas,
-- metas ODS, agendas prioritárias...), e o SIOP marca cada nível (programa,
-- objetivo, entrega, meta...) de forma independente. Por isso o recorte usa os
-- códigos que aparecem em QUALQUER tabela agenda_*_filtrado_mir, e não só em
-- agenda_programa: senão as tabelas fato ficam com códigos órfãos.
{% set tabelas_agenda = [
    "agenda_programa_filtrado_mir",
    "agenda_objetivo_geral_filtrado_mir",
    "agenda_objetivo_especifico_filtrado_mir",
    "agenda_entrega_filtrado_mir",
    "agenda_meta_entrega_filtrado_mir",
    "agenda_meta_objetivo_especifico_filtrado_mir",
    "agenda_indicador_entrega_filtrado_mir",
    "agenda_indicador_objetivo_especifico_filtrado_mir",
    "agenda_desagregacao_meta_entrega_filtrado_mir",
    "agenda_desagregacao_meta_objetivo_especifico_filtrado_mir",
    "agenda_regionalizacao_meta_entrega_filtrado_mir",
    "agenda_regionalizacao_meta_objetivo_especifico_filtrado_mir",
    "agenda_medida_institucional_objetivo_especifico_filtrado_mir",
    "agenda_medida_institucional_programa_filtrado_mir",
] %}

-- As 5 agendas transversais originais do PPA 2024-2027. Em 2024 a ambiental se
-- chama "Agenda Ambiental"; a partir de 2025, "Ambiental".
{% set agendas_transversais = (
    "'Ambiental', 'Povos Indígenas', 'Igualdade Racial', 'Mulheres', "
    "'Crianças e Adolescentes'"
) %}

with
    agenda as (
        select
            *,
            -- 2024 grava o nome em `titulo`; 2025+ em `nome`.
            coalesce(nome, titulo) as nome_agenda,
            regexp_replace(
                coalesce(nome, titulo), '^Agenda Ambiental$', 'Ambiental'
            ) as nome_normalizado
        from {{ ref("agenda") }}
    ),

    codigos_mir as (
        {% for tabela in tabelas_agenda %}
            select distinct codigo_agenda, ano_ppa
            from {{ ref(tabela) }}
            {% if not loop.last %}
                union
            {% endif %}
        {% endfor %}
    ),

    -- De-para entre revisões: em 2025 o SIOP recodificou as agendas (ex.: 5 ->
    -- 369). A chave estável é o código da primeira revisão >= 2025 com o mesmo
    -- nome; de 2025 para 2026 os códigos não mudaram.
    codigo_recente as (
        select distinct on (nome_normalizado) nome_normalizado, codigo
        from agenda
        where ano_ppa >= 2025
        order by nome_normalizado, ano_ppa
    ),

    classificada as (
        select
            agenda.*,
            coalesce(codigo_recente.codigo, agenda.codigo) as chave_agenda,
            case
                when
                    agenda.tipo = 'Agenda Transversal'
                    and agenda.nome_normalizado in ({{ agendas_transversais }})
                then 'Agenda transversal'
                when agenda.tipo in ({{ agendas_transversais }})
                then 'Sub-agenda transversal'
                when agenda.tipo = 'Agenda Transversal'
                then 'Agenda transversal (incluída em 2025)'
                when agenda.tipo like 'ODS %'
                then 'Meta ODS'
                when agenda.tipo in ('Agenda Prioritária', 'Prioridade')
                then 'Agenda prioritária'
                when agenda.tipo = 'Agenda Transversal Territorial'
                then 'Agenda transversal territorial'
                else agenda.tipo
            end as grupo_agenda,
            -- Agrupador para o BI: sub-agendas apontam para a agenda-mãe (o
            -- `tipo` delas é o nome da mãe); metas ODS para o ODS ("ODS 16").
            case
                when agenda.tipo in ({{ agendas_transversais }})
                then agenda.tipo
                when agenda.tipo like 'ODS %'
                then agenda.tipo
                else agenda.nome_normalizado
            end as nome_agenda_mae
        from agenda
        left join codigo_recente using (nome_normalizado)
    )

select
    classificada.exercicio,
    classificada.codigo,
    classificada.titulo,
    classificada.descricao,
    classificada.tipo,
    classificada.nome,
    classificada.nome_agenda,
    classificada.chave_agenda,
    classificada.grupo_agenda,
    classificada.nome_agenda_mae,
    mae.codigo as codigo_agenda_mae,
    classificada.grupo_agenda
    in ('Agenda transversal', 'Sub-agenda transversal') as pertence_agenda_transversal,
    classificada.ano_ppa,
    classificada.id_hash,
    classificada.dt_ingest
from classificada
inner join
    codigos_mir
    on classificada.codigo = codigos_mir.codigo_agenda
    and classificada.ano_ppa = codigos_mir.ano_ppa
left join
    agenda as mae
    on mae.nome_normalizado = classificada.nome_agenda_mae
    and mae.ano_ppa = classificada.ano_ppa
