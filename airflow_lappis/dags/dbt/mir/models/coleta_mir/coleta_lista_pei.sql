{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 3.3 do formulário de TEDs (alinhamento ao Planejamento
  Estratégico Institucional): as áreas do MIR e a cascata do PEI 2023-2026.

  área -> área mãe (diretoria -> secretaria)
  objetivo estratégico -> objetivo específico -> indicador/meta

  Área e objetivo estratégico são N:N, então o par fica em coleta_lista_pei_area_objetivo.
  O objetivo específico tem uma área só, em chave_area, para o formulário mostrar os
  objetivos da área escolhida dentro de um objetivo estratégico compartilhado.

  Tudo vem dos seeds coleta_pei_*, que registram as fontes públicas. Há só uma revisão do
  PEI, por isso não há in_vigente.
#}
select
    ('area:' || codigo)::text as chave,
    'area'::text as nivel,
    codigo::text as codigo,
    ('area:' || codigo_pai)::text as chave_pai,
    titulo::text as titulo,
    descricao::text as descricao,
    cd_siorg::text as cd_siorg,
    cast(null as text) as tp_objetivo,
    cast(null as text) as chave_area,
    nr_ordem::integer as nr_ordem
from {{ ref("coleta_pei_area") }}

union all

select
    'objetivo_estrategico:' || codigo,
    'objetivo_estrategico',
    codigo,
    null,
    titulo,
    null,
    null,
    tp_objetivo,
    null,
    nr_ordem
from {{ ref("coleta_pei_objetivo_estrategico") }}

union all

select
    chave,
    'objetivo_especifico',
    codigo,
    'objetivo_estrategico:' || codigo_objetivo_estrategico,
    titulo,
    descricao,
    null,
    null,
    'area:' || codigo_area,
    nr_ordem
from {{ ref("coleta_pei_objetivo_especifico") }}

union all

select
    chave,
    'indicador_meta',
    codigo,
    chave_objetivo_especifico,
    titulo,
    null,
    null,
    null,
    null,
    nr_ordem
from {{ ref("coleta_pei_indicador_meta") }}
