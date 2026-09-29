# Etapa 1: Núcleo `execucao_ne` — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar em `mir_silver` o modelo `execucao_ne`, fonte única da execução orçamentária do MIR no grão da linha de empenho do `ppa_tesouro`, com origem do recurso, instrumento vinculado e data de emissão já resolvidos.

**Architecture:** Dois modelos de vínculo no grão da NE (`vinculo_ne_ted`, que consolida a cascata de extração de TED já existente, e `vinculo_ne_convenio`, que aplica a regex de convênio a todas as linhas da NE e valida contra o cadastro do SICONV) alimentam `execucao_ne`, que junta esses vínculos e o código da emenda (`tg_emendas`) às linhas de empenho do `ppa_tesouro`. Nenhum modelo antigo muda nesta etapa.

**Tech Stack:** dbt-core/dbt-postgres 1.7.13, PostgreSQL 17 (container `mir-dump-pg17`, porta 5433, database `analytics`), sqlfmt via poetry.

**Spec:** `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§2, §5 linha `execucao_ne`, §11, §12 item 1).

## Global Constraints

- Schema da silver nova: `mir_silver`. Materialização: `table`.
- A bronze não é alterada. Os modelos silver/gold antigos não são alterados nesta etapa.
- O grão de `execucao_ne` é a linha de empenho do `ppa_tesouro` (`ne_ccor <> '-9'`); a chave é o `id_hash` do bronze.
- Origem do recurso: `Emenda` quando a NE está no `tg_emendas` (`autor_emendas_orcamento`), senão `Recurso próprio`. **Não** usar `resultado_eof_codigo` para classificar (decisão do usuário; fica para depois).
- Precedência do vínculo: TED (cascata existente) > convênio único > `Não identificado`. Mais de um convênio candidato = `ambiguo`, sem chute.
- `emissao_dia = '000/AAAA'` é inscrição de Restos a Pagar: `data_emissao = AAAA-01-01` e `inscricao_rap = true`.
- Comentários no SQL em português, sem acentos, no mesmo estilo dos modelos existentes.
- Todo `.sql` novo passa por `poetry run sqlfmt <arquivo>` antes do commit.
- Commits só com os arquivos da tarefa (`git commit -- <paths>`): existem arquivos de `dicionario-mir/` em stage que **não** fazem parte deste trabalho.

### Ambiente local (usado em todos os comandos)

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
export DB_DW_HOST_MIR=localhost DB_DW_PORT_MIR=5433 DB_DW_USER_MIR=postgres \
       DB_DW_PASSWORD_MIR=postgres DB_DW_DBNAME_MIR=analytics DB_DW_SCHEMA_MIR=mir
docker start mir-dump-pg17
```

Consultas de verificação: `docker exec mir-dump-pg17 psql -U postgres -d analytics -c "<sql>"`.

### Linha de base medida em 2026-09-29 (dump local)

| Medida | Valor |
|---|---|
| Linhas de empenho no `ppa_tesouro` (`ne_ccor <> '-9'`) | 22.247 |
| NEs distintas | 1.835 |
| NEs com plano de TED (cascata) | 210 (1.297 linhas) |
| NEs com convênio candidato válido | 285 (281 únicos, 4 ambíguos) |
| NEs `SICONV` em `execucao_ne` (1 NE com convênio também é TED e fica TED) | 280 (862 linhas) |
| NEs `Não identificado` | 1.345 (20.088 linhas) |
| Linhas `inscricao_rap` | 885 |
| NEs de emenda (`tg_emendas`) | 221, todas presentes no `ppa_tesouro` |
| NEs de emenda sem instrumento | 25 |

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `airflow_lappis/dags/dbt/mir/dbt_project.yml` | Modify | registrar a pasta `mir_silver` no schema `mir_silver` |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_ted.sql` | Create | NE → plano de ação de TED |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql` | Create | NE → convênio do SICONV |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql` | Create | núcleo da execução orçamentária |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` | Create | documentação e testes genéricos dos três modelos |
| `airflow_lappis/dags/dbt/mir/tests/mir_silver/*.sql` | Create | testes singulares de regra de negócio |

---

### Task 0: Preparar o banco local (sem commit)

O dump local tem o `siafi_dbt.ppa_tesouro` anterior ao commit `601121c`, sem a coluna `id_hash`. Em produção a coluna já existe. Este passo só alinha o banco local.

- [ ] **Step 1: Confirmar que a coluna não existe**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -Atc "select count(*) from information_schema.columns where table_schema='siafi_dbt' and table_name='ppa_tesouro' and column_name='id_hash'"
```
Expected: `0`

- [ ] **Step 2: Reconstruir o `ppa_tesouro` a partir da fonte**

Run:
```bash
dbt run --profiles-dir . -s ppa_tesouro --full-refresh
```
Expected: `Completed successfully` e `1 of 1 OK created sql incremental model siafi_dbt.ppa_tesouro`.

- [ ] **Step 3: Verificar grão e unicidade do `id_hash`**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -c "select count(*) linhas, count(distinct id_hash) hashes from siafi_dbt.ppa_tesouro where ne_ccor <> '-9'"
```
Expected: `linhas = 22247`, `hashes = 22247`.

---

### Task 1: `vinculo_ne_ted` (NE → plano de ação de TED)

**Files:**
- Modify: `airflow_lappis/dags/dbt/mir/dbt_project.yml` (bloco `models: mir:`)
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_ted.sql`
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml`
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_ted_plano_unico.sql`

**Interfaces:**
- Consumes: `ref("empenhos_por_plano_acao")` (colunas `ne_ccor text`, `plano_acao integer`, `num_transf text`, `metodo text`); `ref("planos_acao_ted")` (`id_plano_acao integer`).
- Produces: `mir_silver.vinculo_ne_ted` com uma linha por NE: `ne_ccor text` (PK), `id_plano_acao integer`, `num_transf text`, `metodo_ted text`.

- [ ] **Step 1: Registrar a pasta `mir_silver` no projeto**

Em `airflow_lappis/dags/dbt/mir/dbt_project.yml`, dentro de `models: mir:`, depois do bloco `contratos_dbt:`, adicionar:

```yaml
    mir_silver:
      +materialized: table
      +schema: mir_silver
```

- [ ] **Step 2: Escrever o teste singular (falha antes do modelo existir)**

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_ted_plano_unico.sql`:

```sql
-- Falha se alguma NE apontar para mais de um plano de acao na cascata de TED.
-- vinculo_ne_ted consolida por NE com max(); este teste garante que o max()
-- nao esconde conflito entre linhas da mesma NE.
select ne_ccor, count(distinct plano_acao) as qtd_planos
from {{ ref("empenhos_por_plano_acao") }}
where plano_acao is not null
group by ne_ccor
having count(distinct plano_acao) > 1

union all

-- E falha se o modelo perder ou duplicar NEs em relacao a cascata.
select 'contagem divergente' as ne_ccor, 0 as qtd_planos
where
    (select count(*) from {{ ref("vinculo_ne_ted") }})
    <> (
        select count(distinct ne_ccor)
        from {{ ref("empenhos_por_plano_acao") }}
        where plano_acao is not null
    )
```

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml`:

```yaml
version: 2

models:
  - name: vinculo_ne_ted
    description: >
      Vinculo de cada nota de empenho (NE) do ppa_tesouro ao plano de acao de TED,
      no grao da NE. Consolida a cascata de extracao de num_transf de
      empenhos_por_plano_acao (metodos validados um a um); contem apenas NEs com
      plano de acao encontrado. A cascata migra para mir_silver na etapa 3.
    columns:
      - name: ne_ccor
        description: "Numero completo da nota de empenho (UG + gestao + ano + NE + sequencial)."
        tests:
          - unique
          - not_null
      - name: id_plano_acao
        description: "Plano de acao de TED (TransfereGov) ao qual a NE pertence."
        tests:
          - not_null
          - relationships:
              to: ref('planos_acao_ted')
              field: id_plano_acao
      - name: num_transf
        description: "Numero de transferencia extraido da NE e usado para achar o plano."
      - name: metodo_ted
        description: "Metodo(s) da cascata que produziram o vinculo, separados por virgula."
```

- [ ] **Step 3: Rodar o teste e ver falhar**

Run:
```bash
dbt test --profiles-dir . -s vinculo_ne_ted_plano_unico
```
Expected: erro de compilação `Model 'test.mir.vinculo_ne_ted_plano_unico' ... depends on a node named 'vinculo_ne_ted' which was not found`.

- [ ] **Step 4: Implementar o modelo**

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_ted.sql`:

```sql
{{ config(materialized="table") }}

-- Vinculo NE -> plano de acao de TED, no grao da NE.
-- Reaproveita a cascata de extracao de num_transf de empenhos_por_plano_acao
-- (validada metodo a metodo); aqui apenas consolidamos as linhas por NE.
-- Cada NE tem no maximo um plano (garantido pelo teste
-- vinculo_ne_ted_plano_unico), entao max() nao escolhe entre valores.
select
    ne_ccor,
    max(plano_acao) as id_plano_acao,
    max(num_transf) as num_transf,
    string_agg(distinct metodo, ', ' order by metodo) as metodo_ted
from {{ ref("empenhos_por_plano_acao") }}
where plano_acao is not null
group by ne_ccor
```

- [ ] **Step 5: Construir e testar**

Run:
```bash
poetry run sqlfmt models/mir_silver/vinculo_ne_ted.sql tests/mir_silver/vinculo_ne_ted_plano_unico.sql
dbt build --profiles-dir . -s vinculo_ne_ted
```
Expected: `PASS=6 WARN=0 ERROR=0` (1 modelo + 4 testes genéricos + 1 singular).

- [ ] **Step 6: Conferir o volume**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -Atc "select count(*) from mir_silver.vinculo_ne_ted"
```
Expected: `210`

- [ ] **Step 7: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
git add airflow_lappis/dags/dbt/mir/dbt_project.yml \
        airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_ted.sql \
        airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_ted_plano_unico.sql
git commit -m "feat(dbt/mir): vinculo_ne_ted no grao da NE em mir_silver" -- \
        airflow_lappis/dags/dbt/mir/dbt_project.yml \
        airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_ted.sql \
        airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_ted_plano_unico.sql
```

---

### Task 2: `vinculo_ne_convenio` (NE → convênio do SICONV)

**Files:**
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql`
- Modify: `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` (acrescentar o modelo)
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_convenio_consistente.sql`

**Interfaces:**
- Consumes: `ref("ppa_tesouro")` (`ne_ccor`, `ne_info_complementar`, `ne_ccor_descricao`, `doc_observacao`, todos `text`); `ref("convenio")` (`nr_convenio text`).
- Produces: `mir_silver.vinculo_ne_convenio` com uma linha por NE que tem pelo menos um convênio candidato válido: `ne_ccor text` (PK), `qtd_convenios bigint` (>= 1), `nr_convenio text` (preenchido só quando `qtd_convenios = 1`), `fonte_vinculo text` (`info_complementar` | `descricao` | `observacao`).

- [ ] **Step 1: Escrever o teste singular**

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_convenio_consistente.sql`:

```sql
-- Falha se o vinculo NE -> convenio violar suas regras:
--   * nr_convenio so pode vir preenchido quando ha exatamente um candidato;
--   * NE ambigua (mais de um candidato) nao pode escolher um convenio;
--   * todo nr_convenio precisa existir no cadastro do SICONV.
select ne_ccor, 'nr_convenio sem candidato unico' as problema
from {{ ref("vinculo_ne_convenio") }}
where qtd_convenios = 1 and nr_convenio is null

union all

select ne_ccor, 'ambigua com convenio escolhido' as problema
from {{ ref("vinculo_ne_convenio") }}
where qtd_convenios > 1 and nr_convenio is not null

union all

select v.ne_ccor, 'convenio inexistente no SICONV' as problema
from {{ ref("vinculo_ne_convenio") }} as v
left join {{ ref("convenio") }} as c on c.nr_convenio = v.nr_convenio
where v.nr_convenio is not null and c.nr_convenio is null
```

Acrescentar ao final de `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml`:

```yaml
  - name: vinculo_ne_convenio
    description: >
      Vinculo de cada nota de empenho (NE) do ppa_tesouro a um convenio / termo de
      fomento do SICONV, no grao da NE. Testa TODAS as linhas da NE (o
      ne_info_complementar varia entre linhas da mesma NE, em geral com
      placeholders como NAO SE APLICA) e aceita apenas numeros que existem no
      cadastro de convenios. Contem apenas NEs com pelo menos um candidato valido.
    columns:
      - name: ne_ccor
        description: "Numero completo da nota de empenho."
        tests:
          - unique
          - not_null
      - name: qtd_convenios
        description: "Quantidade de convenios distintos encontrados para a NE. Maior que 1 = ambigua."
        tests:
          - not_null
      - name: nr_convenio
        description: "Convenio vinculado; nulo quando a NE e ambigua."
      - name: fonte_vinculo
        description: >
          Campo de onde veio o vinculo, pela prioridade: info_complementar (numero
          puro em ne_info_complementar), descricao (regex em ne_ccor_descricao),
          observacao (regex em doc_observacao).
        tests:
          - accepted_values:
              values: ["info_complementar", "descricao", "observacao"]
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run:
```bash
dbt test --profiles-dir . -s vinculo_ne_convenio_consistente
```
Expected: erro de compilação `depends on a node named 'vinculo_ne_convenio' which was not found`.

- [ ] **Step 3: Implementar o modelo**

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql`:

```sql
{{ config(materialized="table") }}

-- Vinculo NE -> convenio do SICONV, no grao da NE.
-- Mesma regex de convenio usada hoje em numero_transferencia, mas aplicada a
-- TODAS as linhas de cada NE do ppa_tesouro (e nao so as de emendas): o
-- ne_info_complementar varia entre linhas da mesma NE. So contam candidatos
-- que existem no cadastro de convenios; mais de um candidato = NE ambigua.
with
    empenhos as (
        select ne_ccor, ne_info_complementar, ne_ccor_descricao, doc_observacao
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
    ),

    padrao as (
        select
            '(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*(\d{6})'::text as regex_convenio
    ),

    candidatos as (
        select
            ne_ccor,
            1 as prioridade,
            'info_complementar' as fonte,
            ne_info_complementar as nr_candidato
        from empenhos
        where ne_info_complementar ~ '^\d+$'

        union all

        select
            e.ne_ccor,
            2 as prioridade,
            'descricao' as fonte,
            (regexp_match(e.ne_ccor_descricao, p.regex_convenio, 'i'))[1] as nr_candidato
        from empenhos as e
        cross join padrao as p

        union all

        select
            e.ne_ccor,
            3 as prioridade,
            'observacao' as fonte,
            (regexp_match(e.doc_observacao, p.regex_convenio, 'i'))[1] as nr_candidato
        from empenhos as e
        cross join padrao as p
    ),

    convenios as (select distinct nr_convenio from {{ ref("convenio") }}),

    candidatos_validos as (
        select c.*
        from candidatos as c
        inner join convenios as v on v.nr_convenio = c.nr_candidato
    )

select
    ne_ccor,
    count(distinct nr_candidato) as qtd_convenios,
    case
        when count(distinct nr_candidato) = 1 then min(nr_candidato)
    end as nr_convenio,
    (array_agg(fonte order by prioridade))[1] as fonte_vinculo
from candidatos_validos
group by ne_ccor
```

- [ ] **Step 4: Construir e testar**

Run:
```bash
poetry run sqlfmt models/mir_silver/vinculo_ne_convenio.sql tests/mir_silver/vinculo_ne_convenio_consistente.sql
dbt build --profiles-dir . -s vinculo_ne_convenio
```
Expected: `PASS=6 WARN=0 ERROR=0` (1 modelo + 4 testes genéricos + 1 singular).

- [ ] **Step 5: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -c "select count(*) linhas, count(*) filter (where qtd_convenios = 1) unicos, count(*) filter (where qtd_convenios > 1) ambiguos from mir_silver.vinculo_ne_convenio"
```
Expected: `linhas = 285`, `unicos = 281`, `ambiguos = 4`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
git add airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql \
        airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_convenio_consistente.sql
git commit -m "feat(dbt/mir): vinculo_ne_convenio no grao da NE em mir_silver" -- \
        airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql \
        airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/vinculo_ne_convenio_consistente.sql
```

---

### Task 3: `execucao_ne` (núcleo da execução orçamentária)

**Files:**
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql`
- Modify: `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` (acrescentar o modelo)
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_reconciliacao_ppa_tesouro.sql`
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_com_codigo.sql`
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_instrumento_existe.sql`
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_sem_instrumento_limite.sql`

**Interfaces:**
- Consumes: `ref("ppa_tesouro")` (inclusive `id_hash`); `ref("tg_emendas")` (`ne_ccor text`, `autor_emendas_orcamento text`); `ref("vinculo_ne_ted")` e `ref("vinculo_ne_convenio")` das Tasks 1 e 2; `ref("planos_acao_ted")`; `ref("convenio")`.
- Produces: `mir_silver.execucao_ne`, uma linha por linha de empenho do `ppa_tesouro`. As colunas que as etapas 2 a 4 usam:
  - `id_execucao_ne text` (PK, = `id_hash`), `ne_ccor text`
  - `data_emissao date` (not null), `inscricao_rap boolean`, `ne_ccor_ano_emissao integer`
  - `ug_emitente_codigo text`, `ug_responsavel_codigo text`, `ug_responsavel_nome text`
  - `programa_governo`, `programa_governo_descricao`, `acao_governo`, `acao_governo_descricao`, `ptres`, `plano_orcamentario_codigo_uo`, `plano_orcamentario_codigo_funcao`, `plano_orcamentario_codigo_subfuncao`, `plano_orcamentario_codigo_programa`, `plano_orcamentario_codigo_acao`, `plano_orcamentario_codigo_po`, `plano_orcamentario_nome` (todos `text`)
  - `natureza_despesa text`, `natureza_despesa_descricao text`, `grupo_despesa integer`, `grupo_despesa_desc text`, `fonte_recursos_detalhada text`, `fonte_recursos_detalhada_descricao text`, `resultado_eof_codigo integer`, `resultado_eof_nome text`
  - `favorecido_documento text`, `favorecido_nome text`
  - `ne_num_processo`, `ne_info_complementar`, `ne_ccor_descricao`, `doc_observacao` (`text`)
  - `codigo_emenda text` (nulo = recurso próprio), `origem_recurso text` (`Emenda` | `Recurso próprio`)
  - `sistema_instrumento text` (`TED` | `SICONV` | `Não identificado`), `nr_instrumento text` (`id_plano_acao` ou `nr_convenio`), `num_transf text`, `metodo_vinculo text` (`ted: <metodos>` | `convenio: <fonte>` | `ambiguo` | `nao_encontrado`)
  - `despesas_empenhadas`, `despesas_liquidadas`, `despesas_pagas`, `restos_a_pagar_inscritos`, `restos_a_pagar_pagos` (`numeric(15,2)`), `dt_ingest timestamptz`

- [ ] **Step 1: Escrever os testes singulares**

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_reconciliacao_ppa_tesouro.sql`:

```sql
-- Falha se execucao_ne perder, duplicar ou alterar valores em relacao as
-- linhas de empenho do ppa_tesouro (fonte unica da execucao orcamentaria).
with
    fonte as (
        select
            count(*) as linhas,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_liquidadas) as liquidado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos) as rap_inscrito,
            sum(restos_a_pagar_pagos) as rap_pago
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
    ),

    nucleo as (
        select
            count(*) as linhas,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_liquidadas) as liquidado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos) as rap_inscrito,
            sum(restos_a_pagar_pagos) as rap_pago
        from {{ ref("execucao_ne") }}
    )

select f.*, n.*
from fonte as f, nucleo as n
where
    f.linhas <> n.linhas
    or f.empenhado <> n.empenhado
    or f.liquidado <> n.liquidado
    or f.pago <> n.pago
    or f.rap_inscrito <> n.rap_inscrito
    or f.rap_pago <> n.rap_pago
```

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_com_codigo.sql`:

```sql
-- Falha se alguma NE de emenda (tg_emendas) presente no ppa_tesouro ficar sem
-- codigo_emenda / origem Emenda em execucao_ne.
select distinct t.ne_ccor
from {{ ref("tg_emendas") }} as t
inner join {{ ref("execucao_ne") }} as e on e.ne_ccor = t.ne_ccor
where e.codigo_emenda is null or e.origem_recurso <> 'Emenda'
```

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_instrumento_existe.sql`:

```sql
-- Falha se o instrumento vinculado a uma NE nao existir no cadastro de origem,
-- ou se sistema_instrumento e nr_instrumento estiverem incoerentes.
select e.ne_ccor, 'TED sem plano de acao' as problema
from {{ ref("execucao_ne") }} as e
left join {{ ref("planos_acao_ted") }} as p
    on p.id_plano_acao::text = e.nr_instrumento
where e.sistema_instrumento = 'TED' and p.id_plano_acao is null

union all

select e.ne_ccor, 'SICONV sem convenio' as problema
from {{ ref("execucao_ne") }} as e
left join {{ ref("convenio") }} as c on c.nr_convenio = e.nr_instrumento
where e.sistema_instrumento = 'SICONV' and c.nr_convenio is null

union all

select e.ne_ccor, 'Nao identificado com numero' as problema
from {{ ref("execucao_ne") }} as e
where e.sistema_instrumento = 'Não identificado' and e.nr_instrumento is not null
```

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_sem_instrumento_limite.sql`:

```sql
-- Cobertura do vinculo emenda -> instrumento. Linha de base em 2026-09-29: 25
-- NEs de emenda sem instrumento (contratos diretos, SIPAD, convenios antigos).
-- Falha se o numero subir: indica regressao na extracao do vinculo. Subir o
-- limite exige justificativa no PR.
select count(distinct ne_ccor) as nes_emenda_sem_instrumento
from {{ ref("execucao_ne") }}
where origem_recurso = 'Emenda' and sistema_instrumento = 'Não identificado'
having count(distinct ne_ccor) > 25
```

Acrescentar ao final de `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml`:

```yaml
  - name: execucao_ne
    description: >
      Nucleo da execucao orcamentaria do MIR: uma linha por linha de empenho do
      ppa_tesouro (ne_ccor <> '-9'), fonte unica dos valores de empenhado,
      liquidado, pago e restos a pagar para os tres data marts. Cada linha traz a
      origem do recurso (Emenda quando a NE esta no tg_emendas) e o instrumento
      vinculado (TED pela cascata de num_transf, que tem precedencia; senao
      convenio unico do SICONV; senao Nao identificado).
    columns:
      - name: id_execucao_ne
        description: "Chave da linha (id_hash do ppa_tesouro)."
        tests:
          - unique
          - not_null
      - name: ne_ccor
        description: "Numero completo da nota de empenho."
        tests:
          - not_null
      - name: data_emissao
        description: >
          Data de emissao da linha. Para inscricao de restos a pagar (emissao_dia
          = 000/AAAA) usa 1 de janeiro do ano AAAA.
        tests:
          - not_null
      - name: inscricao_rap
        description: "Verdadeiro quando a linha e inscricao de restos a pagar (emissao_dia = 000/AAAA)."
        tests:
          - not_null
      - name: ug_emitente_codigo
        description: "UG emitente da NE (6 primeiros digitos de ne_ccor)."
      - name: codigo_emenda
        description: "Codigo da emenda parlamentar (tg_emendas.autor_emendas_orcamento). Nulo = recurso proprio."
      - name: origem_recurso
        description: "Emenda ou Recurso próprio."
        tests:
          - not_null
          - accepted_values:
              values: ["Emenda", "Recurso próprio"]
      - name: sistema_instrumento
        description: "Sistema do instrumento vinculado: TED (TransfereGov), SICONV ou Não identificado."
        tests:
          - not_null
          - accepted_values:
              values: ["TED", "SICONV", "Não identificado"]
      - name: nr_instrumento
        description: "id_plano_acao (TED) ou nr_convenio (SICONV). Nulo quando Não identificado."
      - name: num_transf
        description: "Numero de transferencia do TED, quando houver."
      - name: metodo_vinculo
        description: >
          Como o instrumento foi encontrado: 'ted: <metodos da cascata>',
          'convenio: <campo>', 'ambiguo' (mais de um convenio candidato) ou
          'nao_encontrado'.
        tests:
          - not_null
      - name: despesas_empenhadas
        description: "Valor empenhado na linha."
      - name: despesas_liquidadas
        description: "Valor liquidado na linha."
      - name: despesas_pagas
        description: "Valor pago na linha."
      - name: restos_a_pagar_inscritos
        description: "Restos a pagar inscritos (linhas com inscricao_rap)."
      - name: restos_a_pagar_pagos
        description: "Restos a pagar pagos na linha."
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run:
```bash
dbt test --profiles-dir . -s execucao_ne_reconciliacao_ppa_tesouro
```
Expected: erro de compilação `depends on a node named 'execucao_ne' which was not found`.

- [ ] **Step 3: Implementar o modelo**

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql`:

```sql
{{ config(materialized="table") }}

-- Nucleo da execucao orcamentaria do MIR, no grao da linha de empenho do
-- ppa_tesouro. Todas as NEs de emenda e de TED ja estao no ppa_tesouro, entao
-- os valores vem so daqui: uma NE nunca e somada duas vezes. Os vinculos e a
-- origem do recurso sao resolvidos no grao da NE e replicados nas linhas.
with
    empenhos as (
        select *
        from {{ ref("ppa_tesouro") }}
        -- ne_ccor = '-9' sao linhas de dotacao, sem NE real
        where ne_ccor <> '-9'
    ),

    -- Cada NE pertence a no maximo uma emenda no tg_emendas
    emendas as (
        select distinct ne_ccor, autor_emendas_orcamento as codigo_emenda
        from {{ ref("tg_emendas") }}
    ),

    ted as (select * from {{ ref("vinculo_ne_ted") }}),

    convenio as (select * from {{ ref("vinculo_ne_convenio") }})

select
    e.id_hash as id_execucao_ne,
    e.ne_ccor,

    -- Datas: 000/AAAA e inscricao de restos a pagar do exercicio AAAA
    case
        when e.emissao_dia ~ '^\d{2}/\d{2}/\d{4}$'
        then to_date(e.emissao_dia, 'DD/MM/YYYY')
        when e.emissao_dia ~ '^000/\d{4}$'
        then make_date(right(e.emissao_dia, 4)::integer, 1, 1)
    end as data_emissao,
    coalesce(e.emissao_dia ~ '^000/\d{4}$', false) as inscricao_rap,
    e.ne_ccor_ano_emissao,

    -- Unidades gestoras
    left(e.ne_ccor, 6) as ug_emitente_codigo,
    e.ug_responsavel_codigo,
    e.ug_responsavel_nome,

    -- Classificacao orcamentaria
    e.programa_governo,
    e.programa_governo_descricao,
    e.acao_governo,
    e.acao_governo_descricao,
    e.ptres,
    e.plano_orcamentario_codigo_uo,
    e.plano_orcamentario_codigo_funcao,
    e.plano_orcamentario_codigo_subfuncao,
    e.plano_orcamentario_codigo_programa,
    e.plano_orcamentario_codigo_acao,
    e.plano_orcamentario_codigo_po,
    e.plano_orcamentario_nome,
    e.natureza_despesa,
    e.natureza_despesa_descricao,
    e.grupo_despesa,
    e.grupo_despesa_desc,
    e.fonte_recursos_detalhada,
    e.fonte_recursos_detalhada_descricao,
    e.resultado_eof_codigo,
    e.resultado_eof_nome,

    -- Favorecido
    e.ne_ccor_favorecido as favorecido_documento,
    e.ne_ccor_favorecido_descricao as favorecido_nome,

    -- Textos de origem dos vinculos (mantidos para auditoria)
    e.ne_num_processo,
    e.ne_info_complementar,
    e.ne_ccor_descricao,
    e.doc_observacao,

    -- Origem do recurso
    em.codigo_emenda,
    case
        when em.codigo_emenda is not null then 'Emenda' else 'Recurso próprio'
    end as origem_recurso,

    -- Instrumento: TED tem precedencia; convenio so quando unico
    case
        when t.ne_ccor is not null
        then 'TED'
        when c.qtd_convenios = 1
        then 'SICONV'
        else 'Não identificado'
    end as sistema_instrumento,
    case
        when t.ne_ccor is not null
        then t.id_plano_acao::text
        when c.qtd_convenios = 1
        then c.nr_convenio
    end as nr_instrumento,
    t.num_transf,
    case
        when t.ne_ccor is not null
        then 'ted: ' || t.metodo_ted
        when c.qtd_convenios = 1
        then 'convenio: ' || c.fonte_vinculo
        when c.qtd_convenios > 1
        then 'ambiguo'
        else 'nao_encontrado'
    end as metodo_vinculo,

    -- Valores
    e.despesas_empenhadas,
    e.despesas_liquidadas,
    e.despesas_pagas,
    e.restos_a_pagar_inscritos,
    e.restos_a_pagar_pagos,

    e.dt_ingest
from empenhos as e
left join emendas as em on em.ne_ccor = e.ne_ccor
left join ted as t on t.ne_ccor = e.ne_ccor
left join convenio as c on c.ne_ccor = e.ne_ccor
```

- [ ] **Step 4: Construir e testar**

Run:
```bash
poetry run sqlfmt models/mir_silver/execucao_ne.sql tests/mir_silver/execucao_ne_*.sql
dbt build --profiles-dir . -s execucao_ne
```
Expected: `PASS=15 WARN=0 ERROR=0` (1 modelo + 10 testes genéricos + 4 singulares).

- [ ] **Step 5: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -c "select sistema_instrumento, count(distinct ne_ccor) nes, count(*) linhas from mir_silver.execucao_ne group by 1 order by 1" -c "select count(*) filter (where inscricao_rap) linhas_rap, count(distinct ne_ccor) filter (where origem_recurso = 'Emenda') nes_emenda, count(distinct ne_ccor) filter (where metodo_vinculo = 'ambiguo') nes_ambiguas from mir_silver.execucao_ne"
```
Expected:
```
 sistema_instrumento | nes  | linhas
---------------------+------+--------
 Não identificado    | 1345 |  20088
 SICONV              |  280 |    862
 TED                 |  210 |   1297

 linhas_rap | nes_emenda | nes_ambiguas
------------+------------+--------------
        885 |        221 |            4
```

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
git add airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql \
        airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_reconciliacao_ppa_tesouro.sql \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_com_codigo.sql \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_instrumento_existe.sql \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_sem_instrumento_limite.sql
git commit -m "feat(dbt/mir): nucleo execucao_ne da execucao orcamentaria em mir_silver" -- \
        airflow_lappis/dags/dbt/mir/models/mir_silver/execucao_ne.sql \
        airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_reconciliacao_ppa_tesouro.sql \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_com_codigo.sql \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_instrumento_existe.sql \
        airflow_lappis/dags/dbt/mir/tests/mir_silver/execucao_ne_emendas_sem_instrumento_limite.sql
```

---

### Task 4: Verificação final da etapa

**Files:** nenhum arquivo novo.

- [ ] **Step 1: Construir tudo de `mir_silver` do zero**

Run:
```bash
dbt build --profiles-dir . -s path:models/mir_silver
```
Expected: `PASS=27 WARN=0 ERROR=0` (3 modelos + 18 testes genéricos + 6 singulares).

- [ ] **Step 2: Confirmar que nenhum modelo antigo foi afetado**

Run:
```bash
cd /home/joaoegewarth/data-application-mir
git diff cd93981 --stat -- airflow_lappis/dags/dbt/mir/models ':!airflow_lappis/dags/dbt/mir/models/mir_silver'
```
Expected: saída vazia. (`cd93981` é o último commit antes desta etapa. Não comparar com `main`: a `feat/indicadores` já tem mudanças de modelos em relação a ela.)

- [ ] **Step 3: Lint de SQL do projeto**

Run:
```bash
cd /home/joaoegewarth/data-application-mir
poetry run sqlfmt ./airflow_lappis/dags/dbt --check
```
Expected: nenhum arquivo de `mir_silver` ou `tests/mir_silver` listado como "would be reformatted".

---

## Fora desta etapa (registrado para as próximas)

- **Macros de dimensão, `surrogate_key` e seed do IBGE** passam para a etapa 2 (mart de Convênios), onde são usados pela primeira vez e podem ser testados através das dimensões reais. O spec (§12 item 1) os colocava na etapa 1; a mudança evita macros sem consumidor.
- **Cascata de TED em `mir_silver`:** `vinculo_ne_ted` lê `empenhos_por_plano_acao` (silver antiga). A cascata é movida para `mir_silver` na etapa 3, junto com o mart de TEDs.
- **Origem mista em instrumentos (decisão pendente com o usuário):** os termos de fomento 965040 e 965084 têm NE de emenda em 2024 e NEs de recurso próprio em 2025. A regra "instrumento é de emenda ou próprio" não vale para esses dois casos. Isso afeta `origem_recurso` de `dim_convenio` (etapa 2) e o teste de exclusividade do spec §11. `execucao_ne` não é afetado, porque carrega a origem por NE.
