{{ config(materialized="table") }}

-- Lista em cascata do PPA para o Bloco 3.1 dos formularios do Coleta MIR:
-- programa -> objetivo especifico -> indicador -> meta; entregas penduradas no
-- objetivo especifico e medidas institucionais no programa. So a revisao mais
-- recente do PPA. A meta nao tem codigo proprio na fonte (ver CTE metas).
with
    revisao as (select max(ano_ppa) as ano_ppa from {{ ref("programa_filtrado_mir") }}),

    programas as (
        select distinct
            'programa' as nivel,
            p.programa::text as codigo,
            cast(null as text) as codigo_pai,
            p.titulo::text as titulo,
            p.ano_ppa
        from {{ ref("programa_filtrado_mir") }} as p
        inner join revisao as r on r.ano_ppa = p.ano_ppa
    ),

    objetivos as (
        select distinct
            'objetivo_especifico' as nivel,
            o.objetivo_especifico::text as codigo,
            o.programa::text as codigo_pai,
            o.enunciado::text as titulo,
            o.ano_ppa
        from {{ ref("objetivo_especifico_filtrado_mir") }} as o
        inner join revisao as r on r.ano_ppa = o.ano_ppa
    ),

    indicadores as (
        select distinct
            'indicador' as nivel,
            i.indicador::text as codigo,
            i.objetivo_especifico::text as codigo_pai,
            i.denominacao::text as titulo,
            i.ano_ppa
        from {{ ref("indicador_objetivo_especifico_filtrado_mir") }} as i
        inner join revisao as r on r.ano_ppa = i.ano_ppa
    ),

    -- A meta nao tem codigo na fonte: codigo = indicador + hash do texto da meta.
    -- Estavel enquanto o texto nao muda e independente das demais metas.
    metas as (
        select
            'meta' as nivel,
            m.indicador::text
            || '-'
            || left(md5(m.meta_do_objetivo_especifico::text), 10) as codigo,
            m.indicador::text as codigo_pai,
            m.meta_do_objetivo_especifico::text as titulo,
            m.ano_ppa
        from
            (
                select distinct indicador, meta_do_objetivo_especifico, ano_ppa
                from {{ ref("meta_objetivo_especifico_filtrado_mir") }}
            ) as m
        inner join revisao as r on r.ano_ppa = m.ano_ppa
    ),

    entregas as (
        select distinct
            'entrega' as nivel,
            e.entrega::text as codigo,
            e.objetivo_especifico::text as codigo_pai,
            e.enunciado::text as titulo,
            e.ano_ppa
        from {{ ref("entrega_filtrado_mir") }} as e
        inner join revisao as r on r.ano_ppa = e.ano_ppa
    ),

    medidas as (
        select distinct
            'medida_institucional' as nivel,
            coalesce(
                nullif(mi.medida_institucional_normativa::text, ''),
                md5(mi.enunciado::text)
            ) as codigo,
            mi.programa::text as codigo_pai,
            mi.enunciado::text as titulo,
            mi.ano_ppa
        from {{ ref("medida_institucional_programa_filtrado_mir") }} as mi
        inner join revisao as r on r.ano_ppa = mi.ano_ppa
    )

select *
from programas
union all
select *
from objetivos
union all
select *
from indicadores
union all
select *
from metas
union all
select *
from entregas
union all
select *
from medidas
