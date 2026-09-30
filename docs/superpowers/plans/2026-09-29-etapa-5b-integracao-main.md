# Etapa 5b: Integração com a main — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levar para a remodelagem o que chegou da `main` no rebase de 2026-09-29: portar para o núcleo os cenários novos de identificação do instrumento das NEs (PR #68) e migrar o indicador I3 para os marts.

**Architecture:**
- **Vínculo NE → convênio:** as regex de vínculo passam para macros compartilhadas (`macros/mir_silver/regex_vinculo.sql`), para um teste de fixture conferir a extração. O rótulo "NUM. TRANSFERENCIA"/"SICONV" vira mais uma fonte de candidatos em `vinculo_ne_convenio`.
- **Herança pela NE de origem:** acontece em `execucao_ne`, o único lugar em que TED e convênio já estão resolvidos. A NE sem instrumento próprio que cita "EMPENHO DE ORIGEM: UG/AAAANE######" herda o instrumento da NE de origem.
- **I3:** passa a ler as mesmas tabelas dos marts que o I1, com a mesma regra de programa (importada do I1).

**Tech Stack:** dbt-core/dbt-postgres 1.7.13, PostgreSQL 17 (container `mir-dump-pg17`, porta 5433, database `analytics`), Python 3.11 e pytest, shandy-sqlfmt 0.32.0.

**Spec:** `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§1, §5, §9). Plano anterior: `docs/superpowers/plans/2026-09-29-etapa-5-i1-e-remocao.md`.

## Contexto: o que veio da main

A branch foi rebaseada sobre `origin/main` (`ac96d94`) em 2026-09-29. O conflito entre modificação e remoção em `siconv_dbt/silver/numero_transferencia.sql` e `schema.yaml` foi resolvido mantendo a remoção. Os cenários da Luana (PR #68, commit `d992a94` da main) continuam em `git show origin/main:airflow_lappis/dags/dbt/mir/models/siconv_dbt/silver/numero_transferencia.sql`:

1. **Rótulo explícito:** `NUM. TRANSFERENCIA` ou `SICONV`, seguido do número, no texto da NE, antes da regra de CONVENIO/FOMENTO.
2. **Backfill por NE:** o número achado em qualquer linha vale para a NE toda. O `vinculo_ne_convenio` já trabalha no grão da NE, então este cenário já está coberto.
3. **NSSALDO:** a NE gerada pela rotina de transferência de saldo cita `EMPENHO DE ORIGEM: 810008/2024NE000092`. O cruzamento é pela UG (`left(ne_ccor, 6)`) e pelo sufixo ano+NE+sequencial (`right(ne_ccor, 12)`).

Também vieram os indicadores I2, I3, I7 e I9:
- **I2 e I9:** leem as saídas do I1 (schema `indicadores`), com colunas que não mudaram.
- **I7:** lê só a bronze.
- **I3:** lê `siafi_dbt.ted_resumo_orcamentario`, `emendas.instrumentos_emendas` e `siconv_dbt.resumo_convenios`, que a etapa 5 removeu.

## Global Constraints

- **Pontos de mudança no dbt:** só `models/mir_silver/vinculo_ne_convenio.sql`, `models/mir_silver/execucao_ne.sql`, `models/mir_silver/schema.yml`, a macro nova e os testes novos. Nenhum modelo gold muda: os marts recebem a mudança pelo `execucao_ne`.
- **Precedência do instrumento:** TED da própria NE, depois o convênio da própria NE, depois o TED da NE de origem, depois o convênio da NE de origem, depois `ambiguo` ou `nao_encontrado`. A herança vai só um nível: não segue a origem da origem. Uma referência que casa com mais de uma NE de origem não herda nada.
- **I3:** a lógica de classificação, o universo, os filtros e as quatro saídas não mudam. Mudam só as fontes, como no I1. O programa de governo do TED usa a mesma regra do I1 (maior código de programa entre as NCs do plano), importada do I1 para não divergir.
- **I2, I7 e I9:** não mudam.
- **Paridade:** toda diferença contra a linha de base é listada com a causa na seção "Resultado" deste plano.
- **sqlfmt:** todo `.sql` alterado passa pelo sqlfmt antes do commit.
- **Linha:** até 90 caracteres no Python (black e ruff do `pyproject.toml`).
- **Commits:** `git add -- <paths>` e `git commit ... -- <paths>`. Mensagem: assunto e, num segundo `-m`, só `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **dbt:** nunca rodar `dbt build/run` sem `-s`, nunca usar operadores `+`, nunca `--full-refresh`.

### Ambiente local

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
export DB_DW_HOST_MIR=localhost DB_DW_PORT_MIR=5433 DB_DW_USER_MIR=postgres \
       DB_DW_PASSWORD_MIR=postgres DB_DW_DBNAME_MIR=analytics DB_DW_SCHEMA_MIR=mir
SP=/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad
```

- dbt: `dbt <cmd> --profiles-dir . --no-partial-parse ...`.
- pytest, da raiz: `python3 -m pytest tests/test_plugins/test_indicadores_i1.py tests/test_plugins/test_indicadores_i3.py -q -p no:cacheprovider`.
- sqlfmt, da raiz: `$SP/sqlfmt-venv/bin/sqlfmt <arquivos>`.
- Consultas: `PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -At -c "<sql>"`.
- Descendentes de um modelo (em vez de `+`): parsear e ler o `child_map` de `target/manifest.json` (script na Tarefa 2).

### Linha de base medida em 2026-09-29 (dump local)

| Objeto | Valor |
|---|---|
| NEs com rótulo NUM. TRANSFERENCIA/SICONV e número no cadastro de convênios | 4 (153164152382025NE004636 → 979943, 153164152382025NE004076 → 978310, 153114152352024NE003172 e 153114152352025NE002684 → 972499). Todas já têm esse convênio escolhido, então o rótulo não cria nem muda vínculo |
| NEs com "EMPENHO DE ORIGEM" | 9, todas sem instrumento. 7 apontam para NEs de origem também sem instrumento (UG 810005). 2 (230002000012024NE800001 e 230002000012024NE800002, de emenda) apontam para 810008000012024NE000093 e 810008000012024NE000092, do convênio 965655 (termo de fomento) |
| Valores das 2 NEs NSSALDO que herdam | todas as medidas somam 0: o saldo entra e sai no mesmo mês (RAP inscrito +60.000/−60.000 e +140.000/−140.000). Nenhum total de fato muda |
| NEs de emenda sem instrumento | 7 de 221 → 5 depois da herança |
| Campos do I3 nos marts | objeto e justificativa de `dim_plano_acao` iguais à bronze nos 120 planos; objeto e modalidade de `dim_convenio` iguais ao `resumo_convenios` nos 643 convênios |
| Suítes de indicadores | I1 30, I2+I3+I7+I9 71 (101 no total) |

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `airflow_lappis/dags/dbt/mir/macros/mir_silver/regex_vinculo.sql` | Criar | Regex de convênio, rótulo de transferência e empenho de origem |
| `airflow_lappis/dags/dbt/mir/tests/mir_silver/regex_vinculo_fixtures.sql` | Criar | Extração das regex sobre textos reais conhecidos |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql` | Modificar | Usa as macros; rótulo como fonte de candidatos |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql` | Modificar | Herança do instrumento pela NE de origem |
| `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_heranca_empenho_origem.sql` | Criar | Nenhuma NE deixa de herdar um instrumento conhecido da origem |
| `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_cobertura_emendas.sql` | Modificar | Linha de base do comentário: 5 de 221 |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` | Modificar | Descrição de `metodo_vinculo` e `fonte_vinculo` |
| `airflow_lappis/plugins/indicadores/i1_valor_executado.py` | Modificar | `_programa_por_plano` vira público (`programa_por_plano_ted`) |
| `airflow_lappis/plugins/indicadores/i3_publico_alvo.py` | Modificar | Lê os marts |
| `airflow_lappis/dags/indicadores/mir/i3_publico_alvo_dag.py` | Modificar | `FONTES` dos marts |
| `tests/test_plugins/test_indicadores_i3.py` | Modificar | Entradas no formato dos marts |
| `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md`, `docs/mir-guia-migracao-power-bi.md` | Modificar | I2, I3, I7 e I9; herança pela NE de origem |

---

### Task 1: Macros de regex e rótulo de transferência no vínculo de convênio

**Files:**
- Create: `airflow_lappis/dags/dbt/mir/macros/mir_silver/regex_vinculo.sql`
- Create: `airflow_lappis/dags/dbt/mir/tests/mir_silver/regex_vinculo_fixtures.sql`
- Modify: `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql`, `models/mir_silver/schema.yml`

**Interfaces:**
- Produces: macros `regex_convenio()`, `regex_rotulo_transferencia()`, `regex_empenho_origem()`, cada uma devolvendo um literal SQL de texto. `regex_empenho_origem()` tem dois grupos: `[1]` é a UG de 6 dígitos e `[2]` é o sufixo `AAAANE######`. A Tarefa 2 usa `regex_empenho_origem()`.

- [ ] **Step 1: Escrever o teste de fixture**

Criar `tests/mir_silver/regex_vinculo_fixtures.sql`:

```sql
-- Falha se alguma regex de vinculo NE -> instrumento deixar de extrair o
-- numero esperado de textos reais conhecidos do ppa_tesouro.
with
    casos(regex, texto, esperado) as (
        values
            ('rotulo', 'ATENDER DESPESA,  NUM. TRANSFERENCIA : 947867, REFERENTE', '947867'),
            ('rotulo', 'TED 22/2025, NUM. TRANSFERENCIA: 984056. PROCESSO', '984056'),
            ('rotulo', 'DESTAQUE PARA ATENDER AO TED 00021/2023 - NUM TRANSFERENCIA 948966', '948966'),
            ('rotulo', 'UFSM/FATEC, CONVENIO SICONV 979943/2025 - UFSM/FATEC', '979943'),
            ('rotulo', 'PROJETO NEABI - TED/MIR, SICONV 7AACWU, PROC.', '7AACWU'),
            ('rotulo', 'SERVICO DE REPARO EM BENS IMOVEIS. SICONV SEM NUMERO', null),
            ('convenio', 'EMISSAO DE EMPENHO VISANDO ATENDER TERMO DE FOMENTO 965655/2024', '965655'),
            ('convenio', 'CONVENIO N° 7AAAOI - PREFEITURA', '7AAAOI'),
            ('convenio', 'CONVENIO UFSM/FATEC, PROJETO', null),
            ('origem_ug', 'NSSALDO - EMPENHO DE ORIGEM: 810008/2024NE000093', '810008'),
            ('origem_sufixo', 'NSSALDO - EMPENHO DE ORIGEM: 810008/2024NE000093', '2024NE000093'),
            ('origem_ug', 'EMISSAO DE EMPENHO VISANDO ATENDER TERMO DE FOMENTO', null)
    ),

    extraido as (
        select
            regex,
            texto,
            esperado,
            case
                regex
                when 'rotulo'
                then (regexp_match(texto, {{ regex_rotulo_transferencia() }}, 'i'))[1]
                when 'convenio'
                then (regexp_match(texto, {{ regex_convenio() }}, 'i'))[1]
                when 'origem_ug'
                then (regexp_match(texto, {{ regex_empenho_origem() }}, 'i'))[1]
                when 'origem_sufixo'
                then (regexp_match(texto, {{ regex_empenho_origem() }}, 'i'))[2]
            end as obtido
        from casos
    )

select *
from extraido
where upper(obtido) is distinct from esperado
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `dbt build --profiles-dir . --no-partial-parse -s regex_vinculo_fixtures 2>&1 | grep -E "ERROR|FAIL|PASS|Done\.|macro"`
Expected: erro de compilação: `'regex_rotulo_transferencia' is undefined`.

- [ ] **Step 3: Criar as macros**

Criar `macros/mir_silver/regex_vinculo.sql`:

```sql
{#
    Padroes de extracao do vinculo NE -> instrumento, compartilhados entre os
    modelos e o teste regex_vinculo_fixtures. Cada macro devolve um literal
    SQL de texto para regexp_match(..., 'i').

    regex_convenio: numero depois de CONVENIO/FOMENTO (6 digitos, ou o formato
    alfanumerico adotado a partir de 2026, ex.: 7AACWU).
    regex_rotulo_transferencia: numero depois do rotulo explicito
    "NUM. TRANSFERENCIA" ou "SICONV" (cenario do antigo numero_transferencia,
    PR #68).
    regex_empenho_origem: NE gerada pela rotina de transferencia de saldo
    (NSSALDO), que cita "EMPENHO DE ORIGEM: 810008/2024NE000092"; grupo 1 = UG,
    grupo 2 = ano + NE + sequencial (o right(ne_ccor, 12) da NE de origem).
#}
{% macro regex_convenio() -%}
    '(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*\m(\d{6}|\d[0-9A-Z]{5})\M'
{%- endmacro %}

{% macro regex_rotulo_transferencia() -%}
    '(?:NUM\.?\s*TRANSFERENCIA|SICONV)\s*:?\s*\m(\d{6}|\d[0-9A-Z]{5})\M'
{%- endmacro %}

{% macro regex_empenho_origem() -%}
    'EMPENHO\s+DE\s+ORIGEM:\s*(\d{6})/(\d{4}NE\d{6})'
{%- endmacro %}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `dbt build --profiles-dir . --no-partial-parse -s regex_vinculo_fixtures 2>&1 | grep -E "ERROR|FAIL|Done\."`
Expected: `PASS=1 ... ERROR=0`. Se algum caso falhar, o teste mostra a linha. Corrija a macro, nunca o caso esperado, e só depois de conferir o texto real no `ppa_tesouro`.

- [ ] **Step 5: Guardar a linha de base do vínculo**

```bash
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -At -c \
  "select md5(string_agg(md5(t::text), '' order by md5(t::text))) from mir_silver.vinculo_ne_convenio t" \
  > $SP/vinculo_convenio_antes.md5
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -c \
  "\copy (select * from mir_silver.vinculo_ne_convenio order by ne_ccor) to '$SP/vinculo_convenio_antes.csv' csv header"
```

- [ ] **Step 6: Usar as macros e acrescentar o rótulo em `vinculo_ne_convenio`**

1. Substituir o bloco de comentário do topo (linhas 3–10, de `-- Vinculo NE -> convenio do SICONV` até `-- nr_processo aparece em alguma linha da NE. Sem desempate = NE ambigua.`) por:

```sql
-- Vinculo NE -> convenio do SICONV, no grao da NE.
-- Mesma regra de convenio do antigo numero_transferencia, mas aplicada a
-- TODAS as linhas de cada NE do ppa_tesouro (e nao so as de emendas): o
-- ne_info_complementar varia entre linhas da mesma NE. Aceita os numeros
-- numericos e os alfanumericos adotados a partir de 2026 (ex.: 7AACWU).
-- Fontes de candidatos, por prioridade: ne_info_complementar, rotulo explicito
-- "NUM. TRANSFERENCIA"/"SICONV" (descricao ou observacao), CONVENIO/FOMENTO na
-- descricao e na observacao (regex em macros/mir_silver/regex_vinculo.sql).
-- So contam candidatos que existem no cadastro de convenios. Com mais de um
-- candidato, desempata pelo numero de processo: vence o convenio cujo
-- nr_processo aparece em alguma linha da NE. Sem desempate = NE ambigua.
```

2. Remover a CTE `padrao` inteira (de `    padrao as (` até o `),` que a fecha).

3. Substituir a CTE `candidatos` por:

```sql
    candidatos as (
        select
            ne_ccor,
            1 as prioridade,
            'info_complementar' as fonte,
            upper(ne_info_complementar) as nr_candidato
        from empenhos
        where ne_info_complementar ~* '^(\d+|\d[0-9A-Z]{5})$'

        union all

        select
            ne_ccor,
            2 as prioridade,
            'rotulo' as fonte,
            upper(
                (regexp_match(ne_ccor_descricao, {{ regex_rotulo_transferencia() }}, 'i'))[1]
            ) as nr_candidato
        from empenhos

        union all

        select
            ne_ccor,
            2 as prioridade,
            'rotulo' as fonte,
            upper(
                (regexp_match(doc_observacao, {{ regex_rotulo_transferencia() }}, 'i'))[1]
            ) as nr_candidato
        from empenhos

        union all

        select
            ne_ccor,
            3 as prioridade,
            'descricao' as fonte,
            upper(
                (regexp_match(ne_ccor_descricao, {{ regex_convenio() }}, 'i'))[1]
            ) as nr_candidato
        from empenhos

        union all

        select
            ne_ccor,
            4 as prioridade,
            'observacao' as fonte,
            upper((regexp_match(doc_observacao, {{ regex_convenio() }}, 'i'))[1]) as nr_candidato
        from empenhos
    ),
```

4. Em `models/mir_silver/schema.yml`, na coluna `fonte_vinculo` de `vinculo_ne_convenio`, acrescentar `rotulo` à lista de valores. Localizar com `grep -n "fonte_vinculo" -A4 models/mir_silver/schema.yml`. Se a descrição listar `info_complementar`, `descricao` e `observacao`, incluir `rotulo` (número depois de "NUM. TRANSFERENCIA" ou "SICONV") entre `info_complementar` e `descricao`.

Run (da raiz): `$SP/sqlfmt-venv/bin/sqlfmt airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql airflow_lappis/dags/dbt/mir/tests/mir_silver/regex_vinculo_fixtures.sql && $SP/sqlfmt-venv/bin/sqlfmt --check airflow_lappis/dags/dbt/mir/macros/mir_silver/regex_vinculo.sql`
Expected: formatação aplicada nos dois modelos. A macro passa no `--check`; se não passar, rodar sem `--check` e conferir que o literal da regex não mudou.

- [ ] **Step 7: Build do vínculo e comparação**

Run: `dbt build --profiles-dir . --no-partial-parse -s vinculo_ne_convenio regex_vinculo_fixtures 2>&1 | grep -E "WARN |ERROR|FAIL|Done\."`
Expected: `ERROR=0`.

```bash
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -At -c \
  "select md5(string_agg(md5(t::text), '' order by md5(t::text))) from mir_silver.vinculo_ne_convenio t" \
  | diff - $SP/vinculo_convenio_antes.md5 && echo "vinculo identico"
```

Expected: `vinculo identico`. Se mudar, exportar de novo (`\copy ... to '$SP/vinculo_convenio_depois.csv'`) e comparar com `diff`. A única diferença aceita é `fonte_vinculo` passar a `rotulo` numa das 4 NEs da linha de base; qualquer outra (convênio novo, NE nova ambígua) é investigada antes de seguir.

- [ ] **Step 8: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P=airflow_lappis/dags/dbt/mir
git add -- $P/macros/mir_silver/regex_vinculo.sql $P/tests/mir_silver/regex_vinculo_fixtures.sql \
  $P/models/mir_silver/vinculo_ne_convenio.sql $P/models/mir_silver/schema.yml
git commit -m "feat(dbt/mir): vinculo de convenio aceita o rotulo NUM. TRANSFERENCIA/SICONV" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" \
  -- $P/macros/mir_silver/regex_vinculo.sql $P/tests/mir_silver/regex_vinculo_fixtures.sql \
  $P/models/mir_silver/vinculo_ne_convenio.sql $P/models/mir_silver/schema.yml
```

---

### Task 2: Herança do instrumento pela NE de origem em `execucao_ne`

**Files:**
- Create: `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_heranca_empenho_origem.sql`
- Modify: `airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql`, `models/mir_silver/schema.yml`, `tests/mir_silver/execucao_ne_cobertura_emendas.sql`

**Interfaces:**
- Consumes: `regex_empenho_origem()` (Tarefa 1).
- Produces: novos valores de `execucao_ne.metodo_vinculo`: `'empenho de origem: ted: <metodo>'` e `'empenho de origem: convenio: <fonte>'` (com ` (desempate por processo)` quando a origem teve desempate). `sistema_instrumento`, `nr_instrumento` e `num_transf` herdados da NE de origem.

- [ ] **Step 1: Escrever o teste**

Criar `tests/mir_silver/execucao_ne_heranca_empenho_origem.sql`:

```sql
-- Falha se uma NE sem instrumento cita um empenho de origem (rotina NSSALDO
-- de transferencia de saldo) cujo instrumento e conhecido, e nao herdou esse
-- instrumento. A referencia so vale quando casa com uma unica NE de origem.
with
    nes as (
        select
            ne_ccor,
            max(sistema_instrumento) as sistema_instrumento,
            max(nr_instrumento) as nr_instrumento
        from {{ ref("execucao_ne") }}
        group by ne_ccor
    ),

    referencias as (
        select distinct
            e.ne_ccor,
            m[1] as ug_origem,
            m[2] as sufixo_origem
        from {{ ref("ppa_tesouro") }} as e
        cross join
            lateral regexp_match(
                e.ne_ccor_descricao, {{ regex_empenho_origem() }}, 'i'
            ) as m
        where m is not null
    ),

    origens as (
        select r.ne_ccor, max(o.sistema_instrumento) as sistema_origem,
            max(o.nr_instrumento) as nr_origem
        from referencias as r
        inner join
            nes as o
            on left(o.ne_ccor, 6) = r.ug_origem
            and right(o.ne_ccor, 12) = r.sufixo_origem
            and o.ne_ccor <> r.ne_ccor
        group by r.ne_ccor
        having count(distinct o.ne_ccor) = 1
    )

select d.ne_ccor, d.sistema_instrumento, o.sistema_origem, o.nr_origem
from origens as o
inner join nes as d on d.ne_ccor = o.ne_ccor
where
    o.sistema_origem <> 'Não identificado'
    and (
        d.sistema_instrumento <> o.sistema_origem
        or d.nr_instrumento is distinct from o.nr_origem
    )
```

Observação: a NE com instrumento próprio diferente do da origem também aparece aqui. Pela linha de base, isso não acontece hoje: as 9 NEs NSSALDO estão sem instrumento. Se aparecer depois, o teste acusa e a regra é revista.

- [ ] **Step 2: Rodar e ver falhar**

Run: `dbt build --profiles-dir . --no-partial-parse -s execucao_ne_heranca_empenho_origem 2>&1 | grep -E "FAIL|PASS|ERROR|Done\."`
Expected: `FAIL 2`. As duas NEs são 230002000012024NE800001 e 230002000012024NE800002.

- [ ] **Step 3: Guardar a linha de base do núcleo**

```bash
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -c \
  "\copy (select id_execucao_ne, md5(t::text) from mir_silver.execucao_ne t order by 1) to '$SP/execucao_ne_antes.csv' csv"
```

- [ ] **Step 4: Implementar a herança**

Em `models/mir_silver/execucao_ne.sql`:

1. Depois da CTE `convenio as (select * from {{ ref("vinculo_ne_convenio") }}),`, acrescentar:

```sql
    -- NE gerada pela rotina de transferencia de saldo (NSSALDO): nao traz o
    -- numero do instrumento, mas cita o empenho de origem ("EMPENHO DE ORIGEM:
    -- 810008/2024NE000092"). A NE de origem e achada pela UG (6 primeiros
    -- caracteres) e pelo ano + NE + sequencial (12 ultimos). Referencia que casa
    -- com mais de uma NE nao herda nada.
    referencia_origem as (
        select distinct
            e.ne_ccor,
            m[1] as ug_origem,
            m[2] as sufixo_origem
        from empenhos as e
        cross join
            lateral regexp_match(
                e.ne_ccor_descricao, {{ regex_empenho_origem() }}, 'i'
            ) as m
        where m is not null
    ),

    empenho_origem as (
        select r.ne_ccor, min(o.ne_ccor) as ne_origem
        from referencia_origem as r
        inner join
            (select distinct ne_ccor from empenhos) as o
            on left(o.ne_ccor, 6) = r.ug_origem
            and right(o.ne_ccor, 12) = r.sufixo_origem
            and o.ne_ccor <> r.ne_ccor
        group by r.ne_ccor
        having count(distinct o.ne_ccor) = 1
    ),
```

2. Substituir o bloco do instrumento (de `    -- Instrumento: TED tem precedencia; senao o convenio escolhido em vinculo_ne_convenio` até `    end as metodo_vinculo,`) por:

```sql
    -- Instrumento: TED tem precedencia; senao o convenio escolhido em
    -- vinculo_ne_convenio; senao o instrumento da NE de origem (NSSALDO), com a
    -- mesma precedencia. A heranca vai so um nivel.
    case
        when t.ne_ccor is not null
        then 'TED'
        when c.nr_convenio is not null
        then 'SICONV'
        when t_o.ne_ccor is not null
        then 'TED'
        when c_o.nr_convenio is not null
        then 'SICONV'
        else 'Não identificado'
    end as sistema_instrumento,
    case
        when t.ne_ccor is not null
        then t.id_plano_acao::text
        when c.nr_convenio is not null
        then c.nr_convenio
        when t_o.ne_ccor is not null
        then t_o.id_plano_acao::text
        when c_o.nr_convenio is not null
        then c_o.nr_convenio
    end as nr_instrumento,
    case
        when t.ne_ccor is not null
        then t.num_transf
        when c.nr_convenio is null and t_o.ne_ccor is not null
        then t_o.num_transf
    end as num_transf,
    case
        when t.ne_ccor is not null
        then 'ted: ' || t.metodo_ted
        when c.nr_convenio is not null and c.desempate_processo
        then 'convenio: ' || c.fonte_vinculo || ' (desempate por processo)'
        when c.nr_convenio is not null
        then 'convenio: ' || c.fonte_vinculo
        when t_o.ne_ccor is not null
        then 'empenho de origem: ted: ' || t_o.metodo_ted
        when c_o.nr_convenio is not null and c_o.desempate_processo
        then
            'empenho de origem: convenio: '
            || c_o.fonte_vinculo
            || ' (desempate por processo)'
        when c_o.nr_convenio is not null
        then 'empenho de origem: convenio: ' || c_o.fonte_vinculo
        when c.qtd_convenios > 1
        then 'ambiguo'
        else 'nao_encontrado'
    end as metodo_vinculo,
```

(A linha antiga `    t.num_transf,` fica dentro do bloco substituído, porque está entre `nr_instrumento` e `metodo_vinculo`. Conferir com `grep -n "num_transf" models/mir_silver/execucao_ne.sql` que sobrou só a expressão nova.)

3. Nos joins do fim, depois de `left join convenio as c on c.ne_ccor = e.ne_ccor`, acrescentar:

```sql
left join empenho_origem as eo on eo.ne_ccor = e.ne_ccor
left join ted as t_o on t_o.ne_ccor = eo.ne_origem
left join convenio as c_o on c_o.ne_ccor = eo.ne_origem
```

4. Em `models/mir_silver/schema.yml`, na descrição de `metodo_vinculo` do `execucao_ne`, substituir o texto por:

```yaml
        description: >
          Como o instrumento foi encontrado: 'ted: <metodos da cascata>',
          'convenio: <fonte>', 'convenio: <fonte> (desempate por processo)',
          'empenho de origem: ted: ...' ou 'empenho de origem: convenio: ...'
          (NE da rotina de transferencia de saldo, que herda o instrumento da NE
          citada em "EMPENHO DE ORIGEM"), 'ambiguo' (varios convenios candidatos
          sem desempate) ou 'nao_encontrado'.
```

5. Em `tests/mir_silver/execucao_ne_cobertura_emendas.sql`, trocar `-- Cobertura do vinculo emenda -> instrumento. Linha de base em 2026-09-29: 7 de` / `-- 221 NEs de emenda (3,2%) sem instrumento` por `-- Cobertura do vinculo emenda -> instrumento. Linha de base em 2026-09-29: 5 de` / `-- 221 NEs de emenda (2,3%) sem instrumento`, mantendo o resto do comentário.

Run (da raiz): `$SP/sqlfmt-venv/bin/sqlfmt airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_heranca_empenho_origem.sql airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_cobertura_emendas.sql`

- [ ] **Step 5: Build do núcleo e dos descendentes**

```bash
dbt parse --profiles-dir . --no-partial-parse > /dev/null
python3 - <<'EOF' > $SP/descendentes_execucao_ne.txt
import json
m = json.load(open("target/manifest.json"))
cm = m["child_map"]
inicio = [k for k, n in m["nodes"].items()
          if n["resource_type"] == "model" and n["name"] == "execucao_ne"]
vistos, pilha = set(), list(inicio)
while pilha:
    n = pilha.pop()
    if n not in vistos:
        vistos.add(n)
        pilha += cm.get(n, [])
print(" ".join(sorted(m["nodes"][k]["name"] for k in vistos if k.startswith("model."))))
EOF
wc -w $SP/descendentes_execucao_ne.txt
dbt build --profiles-dir . --no-partial-parse -s $(cat $SP/descendentes_execucao_ne.txt) \
  2>&1 | grep -E "WARN |ERROR|FAIL|Done\."
```

Expected: `ERROR=0`, com `execucao_ne_heranca_empenho_origem` em PASS. O único `WARN` aceito é o `convenio_mir_complemento_proprio`.

- [ ] **Step 6: Comparar com a linha de base**

```bash
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -c \
  "\copy (select id_execucao_ne, md5(t::text) from mir_silver.execucao_ne t order by 1) to '$SP/execucao_ne_depois.csv' csv"
diff $SP/execucao_ne_antes.csv $SP/execucao_ne_depois.csv | grep '^>' | cut -d, -f1 | tr -d '> ' > $SP/execucao_ne_mudou.txt
wc -l < $SP/execucao_ne_mudou.txt
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -c \
  "select ne_ccor, sistema_instrumento, nr_instrumento, metodo_vinculo, count(*)
   from mir_silver.execucao_ne
   where id_execucao_ne in ($(sed "s/.*/'&'/" $SP/execucao_ne_mudou.txt | paste -sd,))
   group by 1, 2, 3, 4"
```

Expected: 4 linhas mudaram (2 por NE). São as NEs 230002000012024NE800001 e 230002000012024NE800002, agora com `SICONV`, `965655` e `empenho de origem: convenio: info_complementar`. Qualquer outra linha alterada é investigada.

Run: `PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -At -c "select sum(despesas_empenhadas), sum(despesas_pagas), sum(restos_a_pagar_inscritos_acumulavel) from mir_emendas.fato_execucao_orcamentaria"`
Expected: os mesmos totais de antes (empenhado 55.822.240,37), porque as NEs herdadas somam zero.

- [ ] **Step 7: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P=airflow_lappis/dags/dbt/mir
git add -- $P/models/mir_silver/execucao_ne.sql $P/models/mir_silver/schema.yml \
  $P/tests/mir_silver/execucao_ne_heranca_empenho_origem.sql $P/tests/mir_silver/execucao_ne_cobertura_emendas.sql
git commit -m "feat(dbt/mir): NE de transferencia de saldo herda o instrumento do empenho de origem" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" \
  -- $P/models/mir_silver/execucao_ne.sql $P/models/mir_silver/schema.yml \
  $P/tests/mir_silver/execucao_ne_heranca_empenho_origem.sql $P/tests/mir_silver/execucao_ne_cobertura_emendas.sql
```

---

### Task 3: I3 lê os marts

**Files:**
- Modify: `airflow_lappis/plugins/indicadores/i1_valor_executado.py` (renomear `_programa_por_plano`)
- Modify: `airflow_lappis/plugins/indicadores/i3_publico_alvo.py`, `airflow_lappis/dags/indicadores/mir/i3_publico_alvo_dag.py`
- Test: `tests/test_plugins/test_indicadores_i3.py`

**Interfaces:**
- Produces:
  - `programa_por_plano_ted(creditos_teds, acoes_teds) -> dict[Any, str]` em `indicadores.i1_valor_executado` (antes `_programa_por_plano`).
  - `montar_instrumentos_ted(planos, creditos_teds, acoes_teds) -> list[dict]`
  - `montar_instrumentos_convenio(convenios, posicao_convenios, convenentes, ano_corte=ANO_CORTE) -> list[dict]`
  - `calcular_i3(planos, creditos_teds, acoes_teds, convenios, posicao_convenios, convenentes) -> dict[str, list[dict]]`
  - Entradas: `planos` = `mir_teds.dim_plano_acao`; `creditos_teds` = `mir_teds.fato_credito_descentralizado`; `acoes_teds` = `mir_teds.dim_acao_orcamentaria`; `convenios` = `mir_convenios.dim_convenio`; `posicao_convenios` = `mir_convenios.fato_convenio_posicao`; `convenentes` = `mir_convenios.dim_convenente`.
  - As saídas (`i3_publico_alvo_instrumentos`, `i3_publico_alvo_resumo`, `i3_ted_publico_alvo_grupos`, `i3_convenio_publico_alvo_grupos`) e suas colunas não mudam.

- [ ] **Step 1: Tornar público o programa do TED no I1**

Em `airflow_lappis/plugins/indicadores/i1_valor_executado.py`, renomear `_programa_por_plano` para `programa_por_plano_ted` (definição e a única chamada, em `calcular_teds`). Acrescentar ao docstring da função: `Usada também pelo I3.`

Run: `python3 -m pytest tests/test_plugins/test_indicadores_i1.py -q -p no:cacheprovider 2>&1 | grep -E "passed|failed"`
Expected: `30 passed`.

- [ ] **Step 2: Reescrever os testes afetados do I3**

Em `tests/test_plugins/test_indicadores_i3.py`:

1. Substituir os helpers `_plano` e `_convenio` (do `def _plano(` até o `return base` do `_convenio`) por:

```python
def _sk(id_plano_acao):
    """Chave do plano diferente do número (como o hash dos marts); -1 é o membro -1."""
    return -1 if id_plano_acao == -1 else 10_000 + id_plano_acao


def _plano(id_plano_acao, situacao="APROVADO", **extra):
    """Linha de mir_teds.dim_plano_acao."""
    base = {
        "sk_plano_acao": _sk(id_plano_acao),
        "id_plano_acao": id_plano_acao,
        "situacao": situacao,
        "ano": 2024,
        "sigla_unidade_descentralizada": "UFX",
        "origem_recurso": "Recurso próprio",
        "objeto": "",
        "justificativa": "",
    }
    base.update(extra)
    return base


def _nc(id_plano_acao, ptres):
    """Linha de mir_teds.fato_credito_descentralizado (só as colunas usadas)."""
    return {"sk_plano_acao": _sk(id_plano_acao), "ptres": ptres}


def _acao(ptres, codigo_programa):
    """Linha de mir_teds.dim_acao_orcamentaria (só as colunas usadas)."""
    return {"ptres": ptres, "codigo_programa": codigo_programa}


def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              origem="Recurso próprio", objeto="", **extra):
    """Um convênio com os campos de dim_convenio e o nome do convenente."""
    base = {
        "nr_convenio": nr,
        "modalidade": "CONVENIO",
        "origem_recurso": origem,
        "data_assinatura": assinatura,
        "data_inicio_vigencia": vigencia,
        "situacao": situacao,
        "objeto": objeto,
        "convenente_nome": "Prefeitura",
    }
    base.update(extra)
    return base


def _fontes_convenios(especificacoes):
    """Separa os convênios em dim_convenio, posição e dim_convenente, ligados por sk."""
    fontes = {"convenios": [], "posicao_convenios": [], "convenentes": []}
    for i, c in enumerate(especificacoes, start=1):
        fontes["convenios"].append({
            "sk_convenio": i,
            **{k: v for k, v in c.items() if k != "convenente_nome"},
        })
        fontes["posicao_convenios"].append({"sk_convenio": i, "sk_convenente": 100 + i})
        fontes["convenentes"].append(
            {"sk_convenente": 100 + i, "convenente_nome": c["convenente_nome"]}
        )
    return fontes
```

2. Substituir os testes de TED, de `def test_ted_rejeitado_fica_fora_do_universo` até o fim de `test_ted_tipo_e_instrumento_sempre_ted`, por:

```python
def test_ted_rejeitado_fica_fora_do_universo() -> None:
    """Decisão 4: mesmo filtro de situação do I1."""
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    instrumentos = montar_instrumentos_ted(planos, creditos_teds=[], acoes_teds=[])

    assert [i["id_instrumento"] for i in instrumentos] == ["1"]


def test_ted_membro_nao_identificado_fica_fora() -> None:
    planos = [_plano(1), _plano(-1, situacao="Não identificado")]

    instrumentos = montar_instrumentos_ted(planos, [], [])

    assert [i["id_instrumento"] for i in instrumentos] == ["1"]


def test_ted_origem_emenda_pela_origem_recurso() -> None:
    planos = [_plano(1, origem_recurso="Emenda"), _plano(2)]

    instrumentos = montar_instrumentos_ted(planos, [], [])

    assert {i["id_instrumento"]: i["origem"] for i in instrumentos} == {
        "1": "emenda",
        "2": "orcamento_regular",
    }


def test_ted_programa_governo_e_o_maior_programa_das_ncs() -> None:
    """Mesma regra do I1 (e do gold antigo): max(programa) das NCs do plano."""
    planos = [_plano(1), _plano(2)]
    acoes = [_acao("172001", "5802"), _acao("172002", "5804")]
    creditos = [_nc(1, "172001"), _nc(1, "172002")]

    instrumentos = montar_instrumentos_ted(planos, creditos, acoes)

    assert [i["programa_governo"] for i in instrumentos] == ["5804", ""]


def test_ted_classifica_objeto_e_justificativa() -> None:
    planos = [_plano(1, objeto="Formação", justificativa="Comunidades quilombolas")]

    [instr] = montar_instrumentos_ted(planos, [], [])

    assert instr["quilombolas"] == 1


def test_ted_tx_objeto_truncado_em_200_caracteres() -> None:
    planos = [_plano(1, objeto="x" * 300)]

    [instr] = montar_instrumentos_ted(planos, [], [])

    assert len(instr["tx_objeto"]) == 200


def test_ted_tipo_e_instrumento_sempre_ted() -> None:
    [instr] = montar_instrumentos_ted([_plano(1)], [], [])

    assert instr["tipo"] == "TED"
    assert instr["instrumento"] == "TED"
    assert instr["ano"] == "2024"
    assert instr["sigla_executor"] == "UFX"
    assert instr["programa_governo"] == ""  # sem NC
```

3. Substituir os testes de convênio, de `def test_convenio_corte_temporal_2023` até o fim de `test_convenio_classifica_pelo_objeto`, por:

```python
def test_convenio_corte_temporal_2023() -> None:
    fontes = _fontes_convenios([
        _convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01"),
    ])

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["id_instrumento"] for i in instrumentos] == ["2"]


def test_convenio_ano_fallback_para_inicio_vigencia() -> None:
    fontes = _fontes_convenios([_convenio(1, assinatura=None, vigencia="2024-05-10")])

    [instr] = montar_instrumentos_convenio(**fontes)

    assert instr["ano"] == 2024


def test_convenio_exclui_cancelado_e_anulado() -> None:
    fontes = _fontes_convenios([
        _convenio(1, situacao="Cancelado"),
        _convenio(2, situacao="Convênio Anulado"),
        _convenio(3, situacao="Em execução"),
    ])

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["id_instrumento"] for i in instrumentos] == ["3"]


def test_convenio_origem_emenda_pela_origem_recurso() -> None:
    fontes = _fontes_convenios([
        _convenio(1, origem="Emenda"), _convenio(2, origem="Não identificada"),
    ])

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["origem"] for i in instrumentos] == ["emenda", "orcamento_regular"]


def test_convenio_sem_programa_governo_decisao_5() -> None:
    [instr] = montar_instrumentos_convenio(**_fontes_convenios([_convenio(1)]))

    assert instr["programa_governo"] == ""
    assert instr["tipo"] == "Convenio_Fomento"
    assert instr["instrumento"] == "CONVENIO"
    assert instr["sigla_executor"] == "Prefeitura"


def test_convenio_membro_nao_identificado_fica_fora() -> None:
    fontes = _fontes_convenios([_convenio(1)])
    fontes["convenios"].append({
        "sk_convenio": -1, "nr_convenio": "-1", "modalidade": "Não identificado",
        "origem_recurso": "Não identificada", "situacao": "Não identificado",
        "data_assinatura": "2024-01-01", "data_inicio_vigencia": None, "objeto": None,
    })

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["id_instrumento"] for i in instrumentos] == ["1"]


def test_convenio_classifica_pelo_objeto() -> None:
    fontes = _fontes_convenios([_convenio(1, objeto="Apoio a povos indígenas")])

    [instr] = montar_instrumentos_convenio(**fontes)

    assert instr["indigenas"] == 1
    assert instr["leitura_estrita"] == 1
```

4. Substituir o teste de orquestração inteiro por:

```python
def test_calcular_i3_devolve_as_quatro_saidas() -> None:
    saidas = calcular_i3(
        planos=[_plano(1, objeto="Apoio a quilombolas")],
        creditos_teds=[],
        acoes_teds=[],
        **_fontes_convenios([_convenio(1, objeto="Sem menção racial")]),
    )

    assert set(saidas) == {
        "i3_publico_alvo_instrumentos",
        "i3_publico_alvo_resumo",
        "i3_ted_publico_alvo_grupos",
        "i3_convenio_publico_alvo_grupos",
    }
    assert len(saidas["i3_publico_alvo_instrumentos"]) == 2
    assert len(saidas["i3_ted_publico_alvo_grupos"]) == 5
    assert len(saidas["i3_convenio_publico_alvo_grupos"]) == 5
```

5. No docstring do módulo de teste, depois do primeiro parágrafo, acrescentar: `As entradas têm o formato das tabelas dos marts mir_teds e mir_convenios.`

Run: `grep -n "tx_objeto_plano_acao\|resumo=\|instrumentos_emendas\|gold_convenios\|parlamentares" tests/test_plugins/test_indicadores_i3.py`
Expected: nenhuma linha. Se algum teste de `classificar` ou de resumo ainda usar o formato antigo, adaptar só a entrada.

- [ ] **Step 3: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_plugins/test_indicadores_i3.py -q -p no:cacheprovider 2>&1 | grep -E "passed|failed"`
Expected: os testes de TED, de convênio e de orquestração falham (assinaturas antigas). Os de `classificar`, resumo e regressão passam.

- [ ] **Step 4: Reescrever o plugin do I3**

Em `airflow_lappis/plugins/indicadores/i3_publico_alvo.py`:

1. No docstring, substituir o parágrafo `Fontes (tabelas do dbt, iguais às do I1):` e a lista que o segue por:

```
Fontes (tabelas dos marts, as mesmas do I1):
    mir_teds.dim_plano_acao              → objeto, justificativa e origem do TED
    mir_teds.fato_credito_descentralizado → NCs por TED (programa de governo)
    mir_teds.dim_acao_orcamentaria       → programa de cada PTRES
    mir_convenios.dim_convenio           → objeto, modalidade e origem do convênio
    mir_convenios.fato_convenio_posicao  → liga o convênio ao convenente
    mir_convenios.dim_convenente         → nome do convenente

O membro -1 ("Não identificado") das dimensões não entra no universo. O
programa de governo do TED usa a regra do I1 (programa_por_plano_ted).
```

2. Trocar o import `from typing import Any` por:

```python
from typing import Any, Iterable

from indicadores.i1_valor_executado import programa_por_plano_ted
```

e acrescentar, depois de `GRUPOS = [...]`:

```python
MEMBRO_NAO_IDENTIFICADO = "-1"
ORIGEM_EMENDA = "Emenda"
```

3. Substituir `_ano_instrumento` por (e acrescentar os três helpers logo depois):

```python
def _ano_instrumento(r: dict) -> int | None:
    """Ano de referência: data_assinatura, com fallback para o início da vigência."""
    for campo in ("data_assinatura", "data_inicio_vigencia"):
        ano = _ano(r.get(campo))
        if ano is not None:
            return ano
    return None


def _por_chave(linhas: Iterable[dict], campo: str) -> dict[Any, dict]:
    return {r.get(campo): r for r in linhas}


def _membros(linhas: Iterable[dict], campo_sk: str) -> list[dict]:
    """Linhas da dimensão sem o membro -1 (Não identificado)."""
    return [r for r in linhas if _txt(r.get(campo_sk)) != MEMBRO_NAO_IDENTIFICADO]


def _origem(linha: dict) -> str:
    if _txt(linha.get("origem_recurso")) == ORIGEM_EMENDA:
        return "emenda"
    return "orcamento_regular"
```

4. Substituir `montar_instrumentos_ted` e `montar_instrumentos_convenio` por:

```python
def montar_instrumentos_ted(
    planos: list[dict], creditos_teds: list[dict], acoes_teds: list[dict]
) -> list[dict]:
    programa_por_plano = programa_por_plano_ted(creditos_teds, acoes_teds)

    instrumentos = []
    for p in _membros(planos, "sk_plano_acao"):
        if _txt(p.get("situacao")) in SITUACOES_EXCLUIDAS_TED:
            continue

        cats = classificar(p.get("objeto") or "", p.get("justificativa") or "")
        instrumentos.append({
            "tipo": "TED",
            "instrumento": "TED",
            "id_instrumento": _txt(p.get("id_plano_acao")),
            "origem": _origem(p),
            "ano": _txt(p.get("ano")),
            "programa_governo": programa_por_plano.get(p.get("sk_plano_acao"), ""),
            "sigla_executor": _txt(p.get("sigla_unidade_descentralizada")),
            "tx_objeto": _txt(p.get("objeto"))[:200],
            **cats,
        })
    return instrumentos
```

```python
def montar_instrumentos_convenio(
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
    ano_corte: int = ANO_CORTE,
) -> list[dict]:
    posicao = _por_chave(posicao_convenios, "sk_convenio")
    convenente_por_sk = _por_chave(
        _membros(convenentes, "sk_convenente"), "sk_convenente"
    )

    instrumentos = []
    for r in _membros(convenios, "sk_convenio"):
        ano = _ano_instrumento(r)
        if ano is None or ano < ano_corte:
            continue
        if _txt(r.get("situacao")) in SITUACOES_EXCLUIDAS_CONVENIO:
            continue

        pos = posicao.get(r.get("sk_convenio"), {})
        convenente = convenente_por_sk.get(pos.get("sk_convenente"), {})
        cats = classificar(r.get("objeto") or "")
        instrumentos.append({
            "tipo": "Convenio_Fomento",
            "instrumento": _txt(r.get("modalidade")),
            "id_instrumento": _txt(r.get("nr_convenio")),
            "origem": _origem(r),
            "ano": ano,
            "programa_governo": "",  # convênio não tem programa estruturado (decisão 5)
            "sigla_executor": _txt(convenente.get("convenente_nome")),
            "tx_objeto": _txt(r.get("objeto"))[:200],
            **cats,
        })
    return instrumentos
```

5. Substituir `calcular_i3` por:

```python
def calcular_i3(
    planos: list[dict],
    creditos_teds: list[dict],
    acoes_teds: list[dict],
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
) -> dict[str, list[dict]]:
    """Calcula as quatro saídas do I3 a partir das tabelas dos marts."""
    instrumentos_ted = montar_instrumentos_ted(planos, creditos_teds, acoes_teds)
    instrumentos_convenio = montar_instrumentos_convenio(
        convenios, posicao_convenios, convenentes
    )
    todos = instrumentos_ted + instrumentos_convenio
    return {
        "i3_publico_alvo_instrumentos": todos,
        "i3_publico_alvo_resumo": calcular_resumo(todos),
        "i3_ted_publico_alvo_grupos": montar_grupos_ted(instrumentos_ted),
        "i3_convenio_publico_alvo_grupos": montar_grupos_convenio(instrumentos_convenio),
    }
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_plugins/test_indicadores_i1.py tests/test_plugins/test_indicadores_i2.py tests/test_plugins/test_indicadores_i3.py tests/test_plugins/test_indicadores_i7.py tests/test_plugins/test_indicadores_i9.py -q -p no:cacheprovider 2>&1 | grep -E "passed|failed"`
Expected: tudo passando (I1 30; os demais com a contagem nova do I3).

Run: `awk 'length > 90 {print FILENAME": "FNR}' airflow_lappis/plugins/indicadores/i3_publico_alvo.py airflow_lappis/plugins/indicadores/i1_valor_executado.py tests/test_plugins/test_indicadores_i3.py`
Expected: nenhuma linha. As linhas do plano já cabem; se o `fontes_convenios` ou um literal passar de 90, quebrar a linha.

- [ ] **Step 6: Apontar a DAG do I3 para os marts**

Em `airflow_lappis/dags/indicadores/mir/i3_publico_alvo_dag.py`, substituir o comentário e o bloco `FONTES` por:

```python
# Tabelas dos marts lidas pelo indicador -> nome do argumento de calcular_i3.
# Mesmas fontes do I1 (não a saída do I1) — I3 precisa do texto de objeto/
# justificativa, que a saída do I1 não carrega.
FONTES = {
    "planos": ("mir_teds", "dim_plano_acao"),
    "creditos_teds": ("mir_teds", "fato_credito_descentralizado"),
    "acoes_teds": ("mir_teds", "dim_acao_orcamentaria"),
    "convenios": ("mir_convenios", "dim_convenio"),
    "posicao_convenios": ("mir_convenios", "fato_convenio_posicao"),
    "convenentes": ("mir_convenios", "dim_convenente"),
}
```

e, no docstring da DAG, trocar `Lê as tabelas dbt (TED, convênios, emendas)` por `Lê os data marts mir_teds e mir_convenios`.

Run: `python3 -c "import ast; ast.parse(open('airflow_lappis/dags/indicadores/mir/i3_publico_alvo_dag.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 7: Paridade com o I3 antigo**

```bash
git show origin/main:airflow_lappis/plugins/indicadores/i3_publico_alvo.py > $SP/i3_antigo.py
```

Criar `$SP/i3_paridade.py`:

```python
"""Compara o I3 antigo (gold antigo) com o novo (marts) no dump local."""

import sys
from collections import Counter
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, "/home/joaoegewarth/data-application-mir/airflow_lappis/plugins")
sys.path.insert(0, str(Path(__file__).parent))  # i3_antigo.py fica ao lado

import i3_antigo  # noqa: E402
from indicadores import i3_publico_alvo as i3_novo  # noqa: E402

conn = psycopg2.connect(host="localhost", port=5433, user="postgres",
                        password="postgres", dbname="analytics")


def tabela(schema, nome):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"select * from {schema}.{nome}")
        return [dict(r) for r in cur.fetchall()]


antigo = i3_antigo.calcular_i3(
    planos=tabela("siafi_dbt", "planos_acao_ted"),
    resumo=tabela("siafi_dbt", "ted_resumo_orcamentario"),
    instrumentos_emendas=tabela("emendas", "instrumentos_emendas"),
    gold_convenios=tabela("siconv_dbt", "resumo_convenios"),
)
novo = i3_novo.calcular_i3(
    planos=tabela("mir_teds", "dim_plano_acao"),
    creditos_teds=tabela("mir_teds", "fato_credito_descentralizado"),
    acoes_teds=tabela("mir_teds", "dim_acao_orcamentaria"),
    convenios=tabela("mir_convenios", "dim_convenio"),
    posicao_convenios=tabela("mir_convenios", "fato_convenio_posicao"),
    convenentes=tabela("mir_convenios", "dim_convenente"),
)

for saida in antigo:
    print(f"{saida}: antigo {len(antigo[saida])} linhas, novo {len(novo[saida])} linhas")

chave = lambda r: (r["tipo"], str(r["id_instrumento"]))  # noqa: E731
a_linhas = antigo["i3_publico_alvo_instrumentos"]
n_linhas = novo["i3_publico_alvo_instrumentos"]
repetidas = {k: c for k, c in Counter(map(chave, a_linhas)).items() if c > 1}
print(f"\ninstrumentos repetidos no antigo: {len(repetidas)} "
      f"({sum(repetidas.values()) - len(repetidas)} linhas a mais)")
a = {chave(r): r for r in a_linhas}
n = {chave(r): r for r in n_linhas}
print("só no antigo:", sorted(set(a) - set(n)))
print("só no novo:  ", sorted(set(n) - set(a)))
for campo in sorted(set().union(*(r.keys() for r in n_linhas))):
    difs = [(k, a[k].get(campo), n[k].get(campo)) for k in sorted(set(a) & set(n))
            if a[k].get(campo) != n[k].get(campo)]
    print(f"{campo}: {len(difs)} diferentes")
    for k, va, vn in difs[:30]:
        print(f"   {k}: {va!r} -> {vn!r}")

print("\n== resumo (tipo): antigo -> novo")
ra = {r["tipo"]: r for r in antigo["i3_publico_alvo_resumo"]}
rn = {r["tipo"]: r for r in novo["i3_publico_alvo_resumo"]}
for t in sorted(set(ra) | set(rn)):
    va, vn = ra.get(t, {}), rn.get(t, {})
    print(f"   {t}: total {va.get('total_instrumentos')} -> {vn.get('total_instrumentos')}; "
          f"estrita {va.get('leitura_estrita_n')} -> {vn.get('leitura_estrita_n')}; "
          f"ampla {va.get('leitura_ampla_n')} -> {vn.get('leitura_ampla_n')}")
```

Run: `cd /home/joaoegewarth/data-application-mir && python3 $SP/i3_paridade.py > $SP/i3_paridade.txt 2>&1; echo exit=$?; cat $SP/i3_paridade.txt | head -120`
Expected: roda sem erro. As diferenças esperadas, que precisam ser confirmadas uma a uma:
- **Convênios repetidos no antigo:** `resumo_convenios` repetia convênios, então o I3 antigo contava instrumentos a mais.
- **`origem`:** os 23 convênios e os 2 TEDs (4407, 5808) da paridade do I1 passam a `emenda`.
- **Classificação:** `programa_governo`, `ano`, `sigla_executor`, `tx_objeto` e as categorias ficam iguais.
- **`sigla_executor` dos convênios:** é o nome do convenente e pode diferir só onde o `resumo_convenios` repetido trazia outro nome.

Toda diferença fora dessas causas é regressão: parar e reportar.

Acrescentar ao fim deste plano a seção `## Resultado da paridade do I3 (2026-09-29)`, com as linhas por saída, a tabela do resumo (antigo → novo) e as diferenças por causa.

- [ ] **Step 8: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
F="airflow_lappis/plugins/indicadores/i1_valor_executado.py airflow_lappis/plugins/indicadores/i3_publico_alvo.py airflow_lappis/dags/indicadores/mir/i3_publico_alvo_dag.py tests/test_plugins/test_indicadores_i3.py docs/superpowers/plans/2026-09-29-etapa-5b-integracao-main.md"
git add -- $F
git commit -m "feat(indicadores): I3 le os marts mir_teds e mir_convenios" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $F
```

---

### Task 4: Documentação e verificação final

**Files:**
- Modify: `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§1, §5, §9)
- Modify: `docs/mir-guia-migracao-power-bi.md`
- Modify: este plano (seção "Resultado do vínculo")

- [ ] **Step 1: Spec**

1. §1, "Fora de escopo": substituir o item `- Indicadores I2, I3, I7 e I9: estão documentados, mas não existem no código desta branch. Quando forem implementados, já leem o novo gold.` por:

```markdown
- Indicadores I2, I7 e I9 (vieram da main no rebase de 2026-09-29): não mudam. I2 e I9 leem as saídas do I1 (schema `indicadores`), cujas colunas usadas não mudaram, e o I7 lê só a bronze. O I3 lia o gold antigo e passou a ler os marts (§9).
```

2. §5, linha do `execucao_ne`: acrescentar ao fim da coluna "Regras que concentra", antes do `|` final, o texto: `; NE da rotina de transferência de saldo (NSSALDO) sem instrumento próprio herda o da NE citada em "EMPENHO DE ORIGEM" (um nível; cenário do PR #68)`. Na mesma linha, a lista de fontes do `metodo_vinculo` ganha `rótulo NUM. TRANSFERENCIA/SICONV`: trocar `(\`info_complementar\` · \`descricao\` · \`observacao\` · \`nao_encontrado\`)` por `(\`info_complementar\` · \`rotulo\` · \`descricao\` · \`observacao\` · \`empenho de origem\` · \`nao_encontrado\`)`.

3. §9: acrescentar ao fim da lista:

```markdown
- `dags/indicadores/mir/i3_publico_alvo_dag.py` e `plugins/indicadores/i3_publico_alvo.py` (vieram da main): o I3 lê `mir_teds.dim_plano_acao`, `fato_credito_descentralizado` e `dim_acao_orcamentaria`, e `mir_convenios.dim_convenio`, `fato_convenio_posicao` e `dim_convenente`. A classificação não muda; o programa de governo do TED usa a regra do I1 (`programa_por_plano_ted`).
```

- [ ] **Step 2: Guia do Power BI**

Em `docs/mir-guia-migracao-power-bi.md`, substituir o item `- **Indicador I1** (\`indicadores.i1_*\`): ...` (até o fim do parágrafo) por:

```markdown
- **Indicadores** (`indicadores.i1_*`, `i2_*`, `i3_*`, `i9_*`): o I1 e o I3
  passam a ler os marts e mudam pelos mesmos motivos acima (convênios sem
  repetição, origem pela NE). O I2 e o I9 leem as saídas do I1 e acompanham
  essas mudanças. Na saída `i1_ted_por_instrumento`, a coluna
  `n_linhas_resumo` virou `qtd_nes` (quantidade de NEs do plano).
```

- [ ] **Step 3: Verificação final**

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
dbt parse --profiles-dir . --no-partial-parse 2>&1 | grep -E "WARNING|ERROR|Error"
dbt build --profiles-dir . --no-partial-parse -s path:models/mir_silver path:models/mir_convenios path:models/mir_teds path:models/mir_emendas 2>&1 | grep -E "WARN |ERROR|FAIL|Done\."
cd /home/joaoegewarth/data-application-mir
python3 -m pytest tests/test_plugins/test_indicadores_i1.py tests/test_plugins/test_indicadores_i2.py tests/test_plugins/test_indicadores_i3.py tests/test_plugins/test_indicadores_i7.py tests/test_plugins/test_indicadores_i9.py -q -p no:cacheprovider 2>&1 | grep -E "passed|failed"
grep -rn "ted_resumo_orcamentario\|instrumentos_emendas\|resumo_convenios\|nc_plano_acao\|pf_unificado\|ted_empenhos_plano_acao" airflow_lappis/dags airflow_lappis/plugins --include=*.py | grep -v "airflow_lappis/dags/dbt/"
git status --short -- airflow_lappis docs tests
```

Expected:
- parse sem erro;
- build com `ERROR=0` e só o aviso do complemento próprio;
- pytest todo verde;
- o `grep` sem nenhuma linha, porque nenhum indicador lê mais o gold antigo;
- `git status` só com os arquivos desta tarefa.

- [ ] **Step 4: Registrar o resultado e commitar**

Acrescentar ao fim deste plano a seção `## Resultado do vínculo (2026-09-29)`:
- o resultado da comparação do `vinculo_ne_convenio` (Tarefa 1, Step 7);
- as linhas do `execucao_ne` que mudaram (Tarefa 2, Step 6);
- a contagem do build final.

```bash
F="docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md docs/mir-guia-migracao-power-bi.md docs/superpowers/plans/2026-09-29-etapa-5b-integracao-main.md"
git add -- $F
git commit -m "docs(dbt/mir): spec e guia com os indicadores da main e a heranca do empenho de origem" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $F
```

## Fora desta etapa

- Revisão final independente da etapa 5b.
- Descrição do PR.
- Rodar `docs/mir-drop-legado.sql` em produção, depois do deploy e da migração dos painéis. Agora nenhum indicador depende das tabelas antigas.

## Resultado da paridade do I3 (2026-09-29)

Comparação do I3 antigo (plugin da `origin/main` sobre `planos_acao_ted`, `ted_resumo_orcamentario`, `instrumentos_emendas` e `resumo_convenios`) contra o novo (marts), no dump local.

| Saída | Antigo | Novo |
|---|---|---|
| `i3_publico_alvo_instrumentos` | 531 | 342 |
| `i3_publico_alvo_resumo` | 5 | 5 |
| `i3_ted_publico_alvo_grupos` | 590 | 590 |
| `i3_convenio_publico_alvo_grupos` | 2.065 | 1.120 |

| Resumo (tipo) | Total | Leitura estrita | Leitura ampla |
|---|---|---|---|
| TED | 118 → 118 | 110 → 110 | 117 → 117 |
| Convenio_Fomento | 413 → 224 | 261 → 142 | 314 → 171 |
| CONVENIO | 47 → 28 | 25 → 14 | 42 → 25 |
| TERMO DE FOMENTO | 366 → 196 | 236 → 128 | 272 → 146 |
| TOTAL | 531 → 342 | 371 → 252 | 431 → 288 |

**Diferenças por causa:**
- **Convênios repetidos no gold antigo:** 188 convênios apareciam repetidos no `resumo_convenios`, com 189 linhas a mais. O I3 antigo contava cada repetição como instrumento, e isso explica toda a queda nos convênios e termos. Os percentuais de leitura estrita e ampla mudam pouco.
- **Origem Emenda pela NE (25):** os mesmos 23 convênios e 2 TEDs (4407, 5808) da paridade do I1.
- Por instrumento, tipo, ano, programa, executor, objeto, todas as categorias e as duas leituras: 0 diferenças.
