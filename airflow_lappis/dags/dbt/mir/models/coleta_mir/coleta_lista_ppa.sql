{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 3.1 do formulário de TEDs (vinculação ao PPA): a lista em
  cascata dos programas do MIR no PPA, com o que o formulário mostra ou deixa escolher
  depois do programa.

  programa -> objetivo geral, objetivos estratégicos (preenchidos sozinhos)
  programa -> objetivo específico -> entrega
  programa -> medida institucional do programa
  objetivo específico -> medida institucional do objetivo específico

  Entram os itens de todas as revisões do PPA, cada um com o texto da revisão mais
  recente em que aparece. Quem saiu da última revisão fica com in_vigente = false, para
  a resposta antiga do Coleta não apontar para uma linha que sumiu.
#}
with
    revisao as (select max(ano_ppa) as ano_ppa from {{ ref("programa_filtrado_mir") }}),

    nos as (
        select
            'programa' as nivel,
            programa as codigo,
            'programa:' || programa as chave,
            cast(null as text) as chave_pai,
            titulo,
            cast(null as text) as descricao,
            publico_alvo as ds_publico_alvo,
            ano_ppa
        from {{ ref("programa_filtrado_mir") }}

        union all

        select
            'objetivo_geral',
            objetivo,
            'objetivo_geral:' || objetivo,
            'programa:' || programa,
            enunciado,
            descricao,
            null,
            ano_ppa
        from {{ ref("objetivo_geral_filtrado_mir") }}

        union all

        -- O código do objetivo estratégico se repete entre programas (ex.: 1.9).
        select
            'objetivo_estrategico',
            objetivo_estrategico,
            'objetivo_estrategico:' || programa || ':' || objetivo_estrategico,
            'programa:' || programa,
            titulo_objetivo_estrategico,
            null,
            null,
            ano_ppa
        from {{ ref("objetivo_estrategico_programa_filtrado_mir") }}

        union all

        select
            'objetivo_especifico',
            objetivo_especifico,
            'objetivo_especifico:' || objetivo_especifico,
            'programa:' || programa,
            enunciado,
            descricao,
            null,
            ano_ppa
        from {{ ref("objetivo_especifico_filtrado_mir") }}

        union all

        select
            'entrega',
            entrega,
            'entrega:' || entrega,
            'objetivo_especifico:' || objetivo_especifico,
            enunciado,
            descricao,
            null,
            ano_ppa
        from {{ ref("entrega_filtrado_mir") }}

        union all

        select
            'medida_institucional_programa',
            medida_institucional_normativa,
            'medida_institucional_programa:' || medida_institucional_normativa,
            'programa:' || programa,
            enunciado,
            descricao,
            null,
            ano_ppa
        from {{ ref("medida_institucional_programa_filtrado_mir") }}
        -- A revisão de 2024 não traz o código das medidas; elas voltam com código em
        -- 2025.
        where medida_institucional_normativa is not null

        union all

        select
            'medida_institucional_objetivo_especifico',
            medida_institucional_normativa,
            'medida_institucional_objetivo_especifico:' || medida_institucional_normativa,
            'objetivo_especifico:' || objetivo_especifico,
            enunciado,
            descricao,
            null,
            ano_ppa
        from {{ ref("medida_institucional_objetivo_especifico_filtrado_mir") }}
        where medida_institucional_normativa is not null
    ),

    ultima as (select distinct on (chave) * from nos order by chave, ano_ppa desc)

select
    u.chave::text as chave,
    u.nivel::text as nivel,
    u.codigo::text as codigo,
    u.chave_pai::text as chave_pai,
    u.titulo::text as titulo,
    u.descricao::text as descricao,
    u.ds_publico_alvo::text as ds_publico_alvo,
    u.ano_ppa::integer as ano_ppa,
    (u.ano_ppa = r.ano_ppa)::boolean as in_vigente
from ultima as u
cross join revisao as r
