{{ config(materialized="table") }}

{#
  Cascata de métodos de extração de num_transf: cada NE é processada pelo primeiro método
  (nesta ordem) que conseguir extrair um valor; o que sobra passa para o método seguinte.
  Ver schema.yml para a descrição de cada método e docs/superpowers/specs/2026-08-14-*
  para o histórico de como cada padrão foi validado.
#}
{% set bronze_columns = [
    'programa_governo', 'programa_governo_descricao', 'acao_governo', 'acao_governo_descricao',
    'emissao_mes', 'emissao_dia', 'ne_ccor', 'ne_num_processo', 'ne_info_complementar',
    'ne_ccor_descricao', 'doc_observacao', 'natureza_despesa', 'natureza_despesa_descricao',
    'ne_ccor_favorecido', 'ne_ccor_favorecido_descricao', 'ne_ccor_ano_emissao', 'ptres',
    'fonte_recursos_detalhada', 'fonte_recursos_detalhada_descricao', 'despesas_empenhadas',
    'despesas_liquidadas', 'despesas_pagas', 'restos_a_pagar_inscritos', 'restos_a_pagar_pagos',
    'ug_responsavel_codigo', 'ug_responsavel_nome',
    'plano_orcamentario_codigo_uo', 'plano_orcamentario_codigo_funcao',
    'plano_orcamentario_codigo_subfuncao', 'plano_orcamentario_codigo_programa',
    'plano_orcamentario_codigo_acao', 'dt_ingest'
] %}
{% set passthrough_columns = bronze_columns + ['ne', 'orgao_id'] %}
{#
  A partir do método 6 (backfill por ne_ccor) o modelo original já não repassava
  programa_governo/programa_governo_descricao/acao_governo/acao_governo_descricao —
  não documentados no schema.yml final. Preservado aqui para manter o comportamento
  idêntico ao pré-refatoração.
#}
{% set narrow_columns = bronze_columns
    | reject('in', ['programa_governo', 'programa_governo_descricao', 'acao_governo', 'acao_governo_descricao'])
    | list %}
{% set narrow_passthrough = narrow_columns + ['ne', 'orgao_id'] %}

{% set num_transf_methods = fromyaml(ted_num_transf_metodos()) %}

with
base as (
  -- Grao de empenho do modelo unico ppa_tesouro (que sucede
  -- empenhos_tesouro_ted). Exclui as linhas de dotacao (ne_ccor = '-9'),
  -- que nao possuem NE real e nao se aplicam ao vinculo de TED/NC. Alem
  -- das colunas historicas, carrega a UG responsavel e a classificacao do
  -- plano orcamentario para que fiquem disponiveis nas camadas seguintes.
  select
    programa_governo,
    programa_governo_descricao,
    acao_governo,
    acao_governo_descricao,
    emissao_mes,
    emissao_dia,
    ne_ccor,
    ug_responsavel_codigo,
    ug_responsavel_nome,
    plano_orcamentario_codigo_uo,
    plano_orcamentario_codigo_funcao,
    plano_orcamentario_codigo_subfuncao,
    plano_orcamentario_codigo_programa,
    plano_orcamentario_codigo_acao,
    ne_num_processo,
    ne_info_complementar,
    ne_ccor_descricao,
    doc_observacao,
    natureza_despesa,
    natureza_despesa_descricao,
    ne_ccor_favorecido,
    ne_ccor_favorecido_descricao,
    ne_ccor_ano_emissao,
    ptres,
    fonte_recursos_detalhada,
    fonte_recursos_detalhada_descricao,
    despesas_empenhadas,
    despesas_liquidadas,
    despesas_pagas,
    restos_a_pagar_inscritos,
    restos_a_pagar_pagos,
    dt_ingest
  from {{ ref("ppa_tesouro") }}
  where ne_ccor <> '-9'
),
empenhos_sem_vinculo_ted as(
  select
    *,
    right(ne_ccor, 12) as ne,
    left(ne_ccor,6) as orgao_id,
    null as nc,
    null as num_transf,
    'sem vinculo' as metodo
  from base
  where
    ne_ccor_descricao ~* '\bTED[[:space:]:/().-]*(S/?[VN]|S/?VINCULO)'
    or ne_ccor_descricao ~* 'SEM[[:space:]]+VINC[[:space:]]*(ULO|/TED)'
),
empenhos_filtrados as(
  select
    *
  from base
  where
    ne_ccor_descricao !~* '\bTED[[:space:]:/().-]*(S/?[VN]|S/?VINCULO)'
    and ne_ccor_descricao !~* 'SEM[[:space:]]+VINC[[:space:]]*(ULO|/TED)'
),
empenhos_seed as (
  select
    {{ star_except(bronze_columns) }},
    right(ne_ccor, 12) as ne,
    left(ne_ccor, 6) as orgao_id,
    {{ target.schema }}.format_nc(
      regexp_substr(ne_ccor_descricao, '([0-9]{4}NC[0-9]+)')
    ) as nc,
    null::text as num_transf,
    null::text as metodo
  from empenhos_filtrados
)

{% for m in num_transf_methods %}
{% set safe_label = m.label | replace(' ', '_') %}
{% set prev = 'empenhos_seed' if loop.first else 'empenhos_restantes_' ~ (num_transf_methods[loop.index0 - 1].label | replace(' ', '_')) %}
, empenhos_orgaos_{{ safe_label }} as (
    select
        {{ star_except(passthrough_columns) }},
        nc,
        replace(
            (regexp_match({{ m.field }}, '{{ m.regex }}', 'i'))[{{ m.group }}],
            '.',
            ''
        ) as num_transf,
        '{{ m.label }}' as metodo
    from {{ prev }}
)
, empenhos_restantes_{{ safe_label }} as (
    select * from empenhos_orgaos_{{ safe_label }} where num_transf is null and nc is null
)
{% endfor %}

{% set last_label = num_transf_methods[-1].label | replace(' ', '_') %}
, empenhos_teds_invalidos as(
select
    {{ star_except(passthrough_columns) }},
    regexp_substr(ne_ccor_descricao, '((?<![0-9])[0-9]{0,3}NC[0-9]+|[0-9]{5,}NC[0-9]+|[0-9]{4}NC(?![0-9]))') as nc,
    null as num_transf,
    'ted ou nc invalido' as metodo
    from empenhos_restantes_{{ last_label }}
),

empenhos_restantes_teds_invalidos as(
select
    {{ star_except(passthrough_columns) }},
    nc,
    num_transf,
    'vinculo nao encontrado' as metodo
from empenhos_teds_invalidos where num_transf is null AND nc is null
),

raw_union AS (
  select {{ star_except(passthrough_columns) }}, nc, num_transf, metodo from empenhos_sem_vinculo_ted
  {% for m in num_transf_methods %}
  UNION ALL
  select {{ star_except(passthrough_columns) }}, nc, num_transf, metodo from empenhos_orgaos_{{ m.label | replace(' ', '_') }} where num_transf is not null OR nc is not null
  {% endfor %}
  UNION ALL
  select {{ star_except(passthrough_columns) }}, nc, num_transf, metodo from empenhos_teds_invalidos where num_transf is not null OR nc is not null
  UNION ALL
  select {{ star_except(passthrough_columns) }}, nc, num_transf, metodo from empenhos_restantes_teds_invalidos
),

ids_agregados_nc_ccor AS (
    SELECT
        ne_ccor,
        MAX(nc) AS nc,
        MAX(num_transf) AS num_transf
    FROM raw_union
    GROUP BY ne_ccor
),

empenhos_orgaos_metodo_6 AS (
SELECT
    {{ star_except(narrow_passthrough, ['ne_ccor']) }}, ert.ne_ccor,
    COALESCE(ert.nc, r.nc) AS nc,
    COALESCE(ert.num_transf, r.num_transf) AS num_transf,
    -- método calculado dinamicamente
    CASE
        WHEN (ert.nc IS NULL AND r.nc IS NOT NULL)
          OR (ert.num_transf IS NULL AND r.num_transf IS NOT NULL)
        THEN 'metodo 6'
        ELSE ert.metodo
    END AS metodo
    FROM raw_union ert
    LEFT JOIN ids_agregados_nc_ccor r USING (ne_ccor)
),

base_empenhos_orgaos_metodo_7 as (
select
  -- seleciona todas as colunas do órgãos 1, exceto nc e num_transf
      *,
      trim(both ' -' from regexp_replace((regexp_match(
          ne_ccor_descricao,
          'TED [[:space:].:NR∫º°-]*(?:([A-Za-zÀ-ÿ/][A-Za-zÀ-ÿ0-9/ \\-]*)[[:space:]\\-]+)?([0-9]{1,5}(?:[./ \\-][0-9]{2,4})?)',
          'i'
      ))[1], '\s+', ' ', 'g')) AS complemento_ted,
      replace((regexp_match(
          ne_ccor_descricao,
          'TED [[:space:].:NR∫º°-]*(?:([A-Za-zÀ-ÿ/][A-Za-zÀ-ÿ0-9/ \\-]*)[[:space:]\\-]+)?([0-9]{1,5}(?:[./ \\-][0-9]{2,4})?)',
          'i'
      ))[2], '.', '') AS num_ted,
      'metodo 1' as metodo_ted
from empenhos_orgaos_metodo_6),

base_metodo_7 AS (
    SELECT
        *,
        (regexp_match(num_ted, '^([0-9]{1,5})(?:[/.\- ]([0-9]{2,4}))?$'))[1] AS numero_base,
        (regexp_match(num_ted, '^([0-9]{1,5})(?:[/.\- ]([0-9]{2,4}))?$'))[2] AS ano_raw
    FROM base_empenhos_orgaos_metodo_7
),
norm_metodo_7 AS (
    SELECT
        *,
        CASE
            WHEN ano_raw IS NULL THEN NULL
            WHEN length(ano_raw) = 2 THEN
                CASE WHEN ano_raw::int <= 30
                    THEN '20' || ano_raw       -- 24 → 2024
                    ELSE '19' || ano_raw       -- 95 → 1995
                END
            ELSE ano_raw
        END AS ano_normalizado
    FROM base_metodo_7
),
agrupado_metodo_7 AS (
  -- calculamos o ano oficial APENAS para numero_base "longos"
  SELECT
    orgao_id,
    numero_base,
    MAX(ano_normalizado) AS ano_oficial
  FROM norm_metodo_7
  WHERE length(numero_base) >= 3
    AND ano_normalizado IS NOT NULL
  GROUP BY orgao_id, numero_base
),

empenhos_orgaos_metodo_7 as (
SELECT
    a.*,
    g.ano_oficial,
    CASE
      WHEN length(a.numero_base) <= 2
            AND a.ano_normalizado is null
      THEN NULL

      -- se o registro não tem ano, e o numero_base é "longo", e há um ano oficial no grupo -> preencher
      WHEN a.ano_normalizado IS NULL
           AND length(a.numero_base) >= 3
           AND g.ano_oficial IS NOT NULL
      THEN a.numero_base || '/' || g.ano_oficial

      -- se o registro já tem ano_normalizado -> manter esse ano (normalizado)
      WHEN a.ano_normalizado IS NOT NULL
      THEN a.numero_base || '/' || a.ano_normalizado

      -- caso contrário (nenhum ano encontrado) -> deixar só o numero_base
      ELSE a.numero_base
    END AS numero_ted_normalizado
FROM norm_metodo_7 a
LEFT JOIN agrupado_metodo_7 g
  ON a.orgao_id = g.orgao_id
AND a.numero_base = g.numero_base
),

empenhos_restantes_metodo_7 as(
  select * from empenhos_orgaos_metodo_7
  WHERE numero_ted_normalizado is null
),

base_empenhos_orgaos_metodo_8 as (
select
  -- seleciona todas as colunas do órgãos 1, exceto nc e num_transf
      {{ star_except(narrow_passthrough) }},nc,num_transf,metodo,
      trim(both ' -' from regexp_replace((regexp_match(
          doc_observacao,
          'TED [[:space:].:NR∫º°-]*(?:([A-Za-zÀ-ÿ/][A-Za-zÀ-ÿ0-9/ \\-]*)[[:space:]\\-]+)?([0-9]{1,5}(?:[./ \\-][0-9]{2,4})?)',
          'i'
      ))[1], '\s+', ' ', 'g')) AS complemento_ted,
      replace((regexp_match(
          doc_observacao,
          'TED [[:space:].:NR∫º°-]*(?:([A-Za-zÀ-ÿ/][A-Za-zÀ-ÿ0-9/ \\-]*)[[:space:]\\-]+)?([0-9]{1,5}(?:[./ \\-][0-9]{2,4})?)',
          'i'
      ))[2], '.', '') AS num_ted,
      'metodo 2' as metodo_ted
from empenhos_restantes_metodo_7),

base_metodo_8 AS (
    SELECT
        *,
        (regexp_match(num_ted, '^([0-9]{1,5})(?:[/.\- ]([0-9]{2,4}))?$'))[1] AS numero_base,
        (regexp_match(num_ted, '^([0-9]{1,5})(?:[/.\- ]([0-9]{2,4}))?$'))[2] AS ano_raw
    FROM base_empenhos_orgaos_metodo_8
),
norm_metodo_8 AS (
    SELECT
        *,
        CASE
            WHEN ano_raw IS NULL THEN NULL
            WHEN length(ano_raw) = 2 THEN
                CASE WHEN ano_raw::int <= 30
                    THEN '20' || ano_raw       -- 24 → 2024
                    ELSE '19' || ano_raw       -- 95 → 1995
                END
            ELSE ano_raw
        END AS ano_normalizado
    FROM base_metodo_8
),
agrupado_metodo_8 AS (
  -- calculamos o ano oficial APENAS para numero_base "longos"
  -- CORRIGIDO: lia de norm_metodo_7 por engano (copy-paste do método 7) — agora lê do
  -- próprio norm_metodo_8, agrupando os TEDs extraídos de doc_observacao, não de
  -- ne_ccor_descricao.
  SELECT
    orgao_id,
    numero_base,
    MAX(ano_normalizado) AS ano_oficial
  FROM norm_metodo_8
  WHERE length(numero_base) >= 3
    AND ano_normalizado IS NOT NULL
  GROUP BY orgao_id, numero_base
),
empenhos_orgaos_metodo_8 as(
  SELECT
      a.*,
      g.ano_oficial,
      CASE
      WHEN length(a.numero_base) <= 2
            AND a.ano_normalizado is null
      THEN NULL

      -- se o registro não tem ano, e o numero_base é "longo", e há um ano oficial no grupo -> preencher
      WHEN a.ano_normalizado IS NULL
           AND length(a.numero_base) >= 3
           AND g.ano_oficial IS NOT NULL
      THEN a.numero_base || '/' || g.ano_oficial

      -- se o registro já tem ano_normalizado -> manter esse ano (normalizado)
      WHEN a.ano_normalizado IS NOT NULL
      THEN a.numero_base || '/' || a.ano_normalizado

      -- caso contrário (nenhum ano encontrado) -> deixar só o numero_base
      ELSE a.numero_base
    END AS numero_ted_normalizado
  FROM norm_metodo_8 a
  LEFT JOIN agrupado_metodo_8 g
    ON a.orgao_id = g.orgao_id
  AND a.numero_base = g.numero_base
  ),
empenhos_restantes_metodo_8 as(
  select * from empenhos_orgaos_metodo_8
  WHERE numero_ted_normalizado is null
),

union_metodo_7_8 as(
select {{ star_except(narrow_passthrough) }},nc,num_transf,metodo,complemento_ted,num_ted,metodo_ted,numero_base,ano_raw,ano_normalizado,ano_oficial,numero_ted_normalizado, 'TED' as tipo_instrumento
from empenhos_orgaos_metodo_7 WHERE numero_ted_normalizado is not null
UNION ALL
select {{ star_except(narrow_passthrough) }},nc,num_transf,metodo,complemento_ted,num_ted,metodo_ted,numero_base,ano_raw,ano_normalizado,ano_oficial,numero_ted_normalizado, 'TED' as tipo_instrumento
from empenhos_orgaos_metodo_8 WHERE numero_ted_normalizado is not null
UNION ALL
select {{ star_except(narrow_passthrough) }},nc,num_transf,metodo,complemento_ted,num_ted,metodo_ted,numero_base,ano_raw,ano_normalizado,ano_oficial,numero_ted_normalizado, null as tipo_instrumento
from empenhos_restantes_metodo_8),

ids_agregados_num_ted_normalizado as(
select
  orgao_id,
  numero_ted_normalizado,
  MAX(nc) AS nc,
  MAX(num_transf) AS num_transf
from union_metodo_7_8
GROUP BY orgao_id,numero_ted_normalizado
),

empenhos_orgaos_metodo_9 AS (
SELECT
    {{ star_except(narrow_passthrough, ['ne_ccor']) }}, ert.ne_ccor,
    COALESCE(ert.nc, r.nc) AS nc,
    COALESCE(ert.num_transf, r.num_transf) AS num_transf,
    CASE
        WHEN (ert.nc IS NULL AND r.nc IS NOT NULL)
          OR (ert.num_transf IS NULL AND r.num_transf IS NOT NULL)
        THEN 'metodo 9'
        ELSE ert.metodo
    END AS metodo,
    complemento_ted, num_ted, numero_base, ano_raw, ano_normalizado, ano_oficial,
    numero_ted_normalizado AS numero_instrumento, ert.tipo_instrumento
    FROM union_metodo_7_8 ert
    LEFT JOIN ids_agregados_num_ted_normalizado r USING (orgao_id,numero_ted_normalizado)
),
planos_de_acao as (
    select * from {{ ref("num_transf_n_plano_acao") }} where plano_acao is not null
),

-- Metodo pagina gov.br, so para as NEs que a cascata nao ligou a um plano: o
-- numero/ano do TED na numeracao do MIR ("TED Nº 16/2023") resolvido pela
-- pagina do gov.br (ted_gov_br). Parceiros tambem numeram os proprios TEDs
-- ("TED 21/2023-ENAP"), entao a NE so e ligada se a UG emitente recebeu credito
-- (NC) daquele plano, e se os numeros que passam nessa regra levarem a um unico
-- plano.
ne_com_plano as (
    select distinct er.ne_ccor
    from empenhos_orgaos_metodo_9 er
    inner join planos_de_acao pa on er.num_transf = cast(pa.num_transf as text)
),

-- Numero/ano que a pagina liga a um unico plano (a pagina as vezes repete o
-- numero para TEDs diferentes, ex.: 12/2024)
pagina_gov_br as (
    select
        numero_ted, max(id_plano_acao) as id_plano_acao, max(num_transf) as num_transf
    from {{ ref("ted_gov_br") }}
    group by numero_ted
    having count(*) = 1 and count(id_plano_acao) = 1
),

citacoes_gov_br as (
    select distinct
        e.ne_ccor,
        lpad((m[1]::integer)::text, 2, '0')
        || '/'
        || case when length(m[2]) = 2 then '20' || m[2] else m[2] end as numero_ted
    from
        (
            select distinct
                ne_ccor,
                concat_ws(
                    ' | ', ne_ccor_descricao, doc_observacao, ne_info_complementar
                ) as texto
            from {{ ref("ppa_tesouro") }}
            where ne_ccor <> '-9'
        ) as e
    cross join lateral regexp_matches(e.texto, {{ regex_numero_ted() }}, 'gi') as m
    where m[1]::integer > 0 and e.ne_ccor not in (select ne_ccor from ne_com_plano)
),

-- UG que recebeu credito de cada plano: o lado da NC que nao e o MIR
ug_credito as (
    select distinct
        id_plano_acao,
        case
            when relatorio = 'enviadas' then favorecido_doc else ug_emitente
        end as ug_executora
    from {{ ref("nc_plano_acao") }}
    where id_plano_acao is not null
),

vinculo_gov_br as (
    select
        c.ne_ccor,
        max(p.num_transf) as num_transf,
        'pagina gov.br: TED ' || string_agg(distinct c.numero_ted, ', ') as metodo
    from citacoes_gov_br c
    inner join pagina_gov_br p using (numero_ted)
    inner join
        ug_credito u
        on u.id_plano_acao = p.id_plano_acao
        and u.ug_executora = left(c.ne_ccor, 6)
    group by c.ne_ccor
    having count(distinct p.id_plano_acao) = 1
),

empenhos_orgaos_metodo_gov_br as (
SELECT
    {{ star_except(narrow_passthrough, ['ne_ccor']) }}, ert.ne_ccor,
    ert.nc,
    COALESCE(g.num_transf, ert.num_transf) AS num_transf,
    COALESCE(g.metodo, ert.metodo) AS metodo,
    complemento_ted, num_ted, numero_base, ano_raw, ano_normalizado, ano_oficial,
    numero_instrumento, ert.tipo_instrumento
    FROM empenhos_orgaos_metodo_9 ert
    LEFT JOIN vinculo_gov_br g USING (ne_ccor)
),

-- Metodo empenho de origem, so para as NEs ainda sem plano: a NE gerada pela
-- rotina de transferencia de saldo (NSSALDO) nao traz o numero do TED, mas cita
-- o empenho de origem ("EMPENHO DE ORIGEM: 810008/2024NE000092"). A NE de
-- origem e achada pela UG (6 primeiros caracteres) e pelo ano + NE + sequencial
-- (12 ultimos); referencia que casa com mais de uma NE nao herda nada. A
-- heranca vai so um nivel: a origem precisa ter plano pelos metodos acima.
ne_com_plano_proprio as (
    select distinct er.ne_ccor, er.num_transf
    from empenhos_orgaos_metodo_gov_br er
    inner join planos_de_acao pa on er.num_transf = cast(pa.num_transf as text)
),

referencia_origem as (
    select distinct e.ne_ccor, m[1] as ug_origem, m[2] as sufixo_origem
    from {{ ref("ppa_tesouro") }} e
    cross join
        lateral regexp_match(e.ne_ccor_descricao, {{ regex_empenho_origem() }}, 'i') as m
    where
        e.ne_ccor <> '-9'
        and m is not null
        and e.ne_ccor not in (select ne_ccor from ne_com_plano_proprio)
),

empenho_origem as (
    select r.ne_ccor, min(o.ne_ccor) as ne_origem
    from referencia_origem r
    inner join
        (select distinct ne_ccor from {{ ref("ppa_tesouro") }} where ne_ccor <> '-9') o
        on left(o.ne_ccor, 6) = r.ug_origem
        and right(o.ne_ccor, 12) = r.sufixo_origem
        and o.ne_ccor <> r.ne_ccor
    group by r.ne_ccor
    having count(distinct o.ne_ccor) = 1
),

vinculo_empenho_origem as (
    select
        eo.ne_ccor,
        max(p.num_transf) as num_transf,
        'empenho de origem: ' || max(eo.ne_origem) as metodo
    from empenho_origem eo
    inner join ne_com_plano_proprio p on p.ne_ccor = eo.ne_origem
    group by eo.ne_ccor
    having count(distinct p.num_transf) = 1
),

empenhos_orgaos_metodo_origem as (
SELECT
    {{ star_except(narrow_passthrough, ['ne_ccor']) }}, ert.ne_ccor,
    ert.nc,
    COALESCE(o.num_transf, ert.num_transf) AS num_transf,
    COALESCE(o.metodo, ert.metodo) AS metodo,
    complemento_ted, num_ted, numero_base, ano_raw, ano_normalizado, ano_oficial,
    numero_instrumento, ert.tipo_instrumento
    FROM empenhos_orgaos_metodo_gov_br ert
    LEFT JOIN vinculo_empenho_origem o USING (ne_ccor)
),
empenhos_restantes_metodo_9 as (
    select * from empenhos_orgaos_metodo_origem where (nc != '') or (num_transf is not null)
),
result_table as (
    select distinct er.*, pa.plano_acao::integer as plano_acao, pa.num_transf as num_transf_pa
    from empenhos_restantes_metodo_9 er
    left join planos_de_acao pa
    on er.num_transf=CAST(pa.num_transf AS TEXT)
)  --

select *
from result_table
