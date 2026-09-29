# Etapa 2a: Silver de Convênios — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar em `mir_silver` os modelos de convênio que alimentam o mart `mir_convenios` (etapa 2b): o recorte dos convênios do MIR com origem do recurso, os movimentos financeiros, o cronograma de desembolso, os eventos administrativos e as contagens de metas e licitações.

**Architecture:** `convenio_mir` define o universo (643 convênios) e é a única fonte do recorte do MIR: os outros modelos filtram a bronze pelos seus `nr_convenio`. Cada modelo tem uma entidade só, no grão natural, sem repetir colunas do convênio. As regras de negócio (recorte, origem do recurso, normalização dos tipos de movimento e evento, limpeza de duplicatas da origem) ficam aqui; dimensões e fatos são da etapa 2b.

**Tech Stack:** dbt-core/dbt-postgres 1.7.13, PostgreSQL 17 (container `mir-dump-pg17`, porta 5433, database `analytics`), shandy-sqlfmt 0.32.0.

**Spec:** `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§2, §5 linhas de convênio, §6).

## Global Constraints

- Schema `mir_silver`, materialização `table` (já configurado em `dbt_project.yml` para a pasta `models/mir_silver`).
- Nenhum modelo existente é alterado. Bronze intocada.
- Recorte do MIR (regra atual de `convenios_consolidados`): convênio com `ug_emitente = 810008` **ou** com NE da UG 810008 vinculada em `execucao_ne` (`sistema_instrumento = 'SICONV'` e `ug_emitente_codigo = '810008'`).
- Origem do recurso do convênio (decisões do usuário em 2026-09-29):
  - `Emenda`: alguma NE do convênio em `execucao_ne` (de qualquer UG) tem `origem_recurso = 'Emenda'`;
  - `Recurso próprio`: tem NE em `execucao_ne` e nenhuma é de emenda;
  - `Não identificada`: não tem NE em `execucao_ne`;
  - `complemento_proprio = true`: origem `Emenda` e também tem NE de `Recurso próprio` (complemento até o mínimo legal de R$ 200 mil).
- Os valores literais `Emenda`, `Recurso próprio`, `Não identificada` e os tipos de movimento/evento levam acento (são dados); comentários SQL em português sem acentos.
- Todo `.sql` novo passa pelo sqlfmt antes do commit.
- Commits só com os arquivos da tarefa (`git commit -- <paths>`); há ~90 arquivos de `dicionario-mir/` em stage que não fazem parte deste trabalho. Único trailer permitido: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

### Ambiente local (usado em todos os comandos)

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
export DB_DW_HOST_MIR=localhost DB_DW_PORT_MIR=5433 DB_DW_USER_MIR=postgres \
       DB_DW_PASSWORD_MIR=postgres DB_DW_DBNAME_MIR=analytics DB_DW_SCHEMA_MIR=mir
```

- Todo comando dbt leva `--no-partial-parse` (o cache de parse parcial esconde testes novos).
- sqlfmt (não está no poetry), a partir da raiz do repositório: `/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad/sqlfmt-venv/bin/sqlfmt <arquivos>`.
- Consultas: `docker exec mir-dump-pg17 psql -U postgres -d analytics -c "<sql>"`.

### Linha de base medida em 2026-09-29 (dump local)

| Medida | Valor |
|---|---|
| Convênios do MIR | 643 (igual a `convenios_consolidados`) |
| Modalidade | CONVENIO 402 · TERMO DE FOMENTO 234 · TERMO DE COLABORACAO 6 · TERMO DE PARCERIA 1 |
| Origem | Emenda 189 · Recurso próprio 36 · Não identificada 418 |
| Complemento próprio | 2 (965040, 965084) |
| Movimentos | Desembolso federal 568 (R$ 128.160.017,70) · Contrapartida depositada 291 (R$ 4.599.883,02) · Desbloqueio 0 · Pagamento a fornecedor 20.911 (R$ 100.329.484,72) · Pagamento de tributo 668 (R$ 797.831,78; 28 sem data) |
| Cronograma | 1.177 parcelas (R$ 176.471.172,94) |
| Eventos | Mudança de situação 14.358 · Termo aditivo 468 · Prorrogação de ofício 209 · Solicitação de alteração 747 · Solicitação de rendimento 121 (total 15.903) |
| Contagens | metas 1.648 (R$ 177.994.936,13) · licitações 6.563 (R$ 229.504.133,73) |

Limpezas da origem aplicadas aqui:
- `historico_situacao`: 1.571 linhas idênticas e 984 repetições que só diferem em `dias_historico_sit` (recalculado a cada ingestão). Uma linha por convênio × data × situação, com o maior `dias_historico_sit`.
- `prorroga_oficio`: o convênio 879279 tem duas prorrogações distintas com o mesmo `nr_prorroga`; a chave inclui `dt_inicio_prorroga`.

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_mir.sql` | Create | universo de convênios do MIR, atributos 1:1 da proposta, origem do recurso |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_movimento_financeiro.sql` | Create | desembolso, contrapartida, desbloqueio, pagamento e tributo |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_cronograma.sql` | Create | parcelas previstas de desembolso |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_evento.sql` | Create | eventos administrativos |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_contagens.sql` | Create | contagens de metas e licitações por convênio |
| `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` | Modify | documentação e testes genéricos (acrescentar ao final) |
| `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_*.sql` | Create | testes singulares |

---

### Task 1: `convenio_mir` (universo e origem do recurso)

**Files:**
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_mir.sql`
- Modify: `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` (acrescentar ao final)
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_recorte.sql`
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_origem.sql`

**Interfaces:**
- Consumes: `ref("convenio")` e `ref("proposta")` (bronze SICONV); `ref("execucao_ne")` (`sistema_instrumento`, `nr_instrumento`, `ug_emitente_codigo`, `origem_recurso`, `ug_responsavel_codigo`, `ug_responsavel_nome`).
- Produces: `mir_silver.convenio_mir`, uma linha por convênio, PK `nr_convenio text`. Colunas que a etapa 2b usa: `nr_convenio`, `id_proposta integer`, `nr_processo text`, `modalidade text`, `objeto text`, `situacao text`, `subsituacao text`, `situacao_publicacao text`, `instrumento_ativo text`, `ug_emitente text`, `data_assinatura date`, `data_publicacao date`, `data_inicio_vigencia date`, `data_fim_vigencia date`, `data_fim_vigencia_original date`, `data_limite_prestacao_contas date`, `valor_global_original numeric`, `valor_global numeric`, `valor_repasse numeric`, `valor_contrapartida numeric`, `valor_saldo_conta numeric`, `convenente_documento text` (só dígitos), `convenente_nome text`, `convenente_natureza_juridica text`, `uf text`, `municipio text`, `cod_municipio_ibge text` (7 dígitos), `origem_recurso text`, `complemento_proprio boolean`, `ug_responsavel_codigo text`, `ug_responsavel_nome text` (UGs das NEs, agregadas).

- [ ] **Step 1: Escrever os testes singulares**

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_recorte.sql`:

```sql
-- Falha se o universo de convenios do MIR divergir da regra de recorte:
-- ug_emitente 810008 ou com NE da UG 810008 vinculada no nucleo.
with
    esperado as (
        select nr_convenio
        from {{ ref("convenio") }}
        where ug_emitente = 810008

        union

        select nr_instrumento as nr_convenio
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV' and ug_emitente_codigo = '810008'
    )

select e.nr_convenio, 'faltando em convenio_mir' as problema
from esperado as e
left join {{ ref("convenio_mir") }} as c on c.nr_convenio = e.nr_convenio
where c.nr_convenio is null

union all

select c.nr_convenio, 'fora do recorte' as problema
from {{ ref("convenio_mir") }} as c
left join esperado as e on e.nr_convenio = c.nr_convenio
where e.nr_convenio is null
```

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_origem.sql`:

```sql
-- Falha se a origem do recurso do convenio contradisser as NEs do nucleo:
--   * Emenda exige alguma NE de emenda;
--   * Recurso proprio exige NE e nenhuma de emenda;
--   * Nao identificada exige ausencia de NE;
--   * complemento_proprio so em Emenda com NE de recurso proprio.
with
    nes as (
        select
            nr_instrumento as nr_convenio,
            bool_or(origem_recurso = 'Emenda') as tem_emenda,
            bool_or(origem_recurso = 'Recurso próprio') as tem_proprio
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV'
        group by nr_instrumento
    )

select c.nr_convenio, c.origem_recurso, c.complemento_proprio
from {{ ref("convenio_mir") }} as c
left join nes as n on n.nr_convenio = c.nr_convenio
where
    (c.origem_recurso = 'Emenda' and not coalesce(n.tem_emenda, false))
    or (
        c.origem_recurso = 'Recurso próprio'
        and (n.nr_convenio is null or n.tem_emenda)
    )
    or (c.origem_recurso = 'Não identificada' and n.nr_convenio is not null)
    or (
        c.complemento_proprio
        <> (c.origem_recurso = 'Emenda' and coalesce(n.tem_proprio, false))
    )
```

Acrescentar ao final de `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml`:

```yaml
  - name: convenio_mir
    description: >
      Universo de convenios, termos de fomento, colaboracao e parceria do MIR no
      SICONV: ug_emitente 810008 ou com NE da UG 810008 vinculada em execucao_ne.
      Uma linha por instrumento, com os atributos 1:1 da proposta (modalidade,
      objeto, convenente, municipio) e a origem do recurso derivada das NEs do
      nucleo.
    columns:
      - name: nr_convenio
        description: "Numero do instrumento no SICONV."
        tests:
          - unique
          - not_null
      - name: modalidade
        description: "Modalidade da proposta: CONVENIO, TERMO DE FOMENTO, TERMO DE COLABORACAO ou TERMO DE PARCERIA."
        tests:
          - not_null
      - name: convenente_documento
        description: "CNPJ do convenente (proponente), so digitos."
        tests:
          - not_null
      - name: cod_municipio_ibge
        description: "Codigo IBGE do municipio do convenente (7 digitos)."
      - name: origem_recurso
        description: >
          Emenda (alguma NE do instrumento e de emenda), Recurso próprio (tem NE e
          nenhuma e de emenda) ou Não identificada (sem NE no nucleo; convenios
          assinados antes do periodo do relatorio do Tesouro).
        tests:
          - not_null
          - accepted_values:
              values: ["Emenda", "Recurso próprio", "Não identificada"]
      - name: complemento_proprio
        description: >
          Verdadeiro quando um instrumento de Emenda tambem recebeu NE de recurso
          proprio (complemento ate o repasse minimo legal de R$ 200 mil).
        tests:
          - not_null
      - name: ug_responsavel_codigo
        description: "UGs responsaveis das NEs vinculadas, separadas por virgula."
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `dbt test --profiles-dir . --no-partial-parse -s convenio_mir_recorte`
Expected: erro de compilação `depends on a node named 'convenio_mir' which was not found`.

- [ ] **Step 3: Implementar o modelo**

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_mir.sql`:

```sql
{{ config(materialized="table") }}

-- Universo de convenios do MIR no SICONV, no grao do instrumento. Mesmo
-- recorte de convenios_consolidados: ug_emitente 810008 ou com NE da UG 810008
-- vinculada no nucleo. A origem do recurso vem das NEs do nucleo (de qualquer
-- UG); sem NE, a origem nao e conhecida.
with
    nes as (
        select
            nr_instrumento as nr_convenio,
            ug_emitente_codigo,
            origem_recurso,
            ug_responsavel_codigo,
            ug_responsavel_nome
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV'
    ),

    recorte as (
        select nr_convenio
        from {{ ref("convenio") }}
        where ug_emitente = 810008

        union

        select nr_convenio
        from nes
        where ug_emitente_codigo = '810008'
    ),

    origem as (
        select
            nr_convenio,
            bool_or(origem_recurso = 'Emenda') as tem_emenda,
            bool_or(origem_recurso = 'Recurso próprio') as tem_proprio,
            string_agg(
                distinct ug_responsavel_codigo, ', ' order by ug_responsavel_codigo
            ) as ug_responsavel_codigo,
            string_agg(
                distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome
            ) as ug_responsavel_nome
        from nes
        group by nr_convenio
    )

select
    c.nr_convenio,
    c.id_proposta,
    c.nr_processo,
    p.modalidade,
    p.objeto_proposta as objeto,

    -- Situacao
    c.sit_convenio as situacao,
    c.subsituacao_conv as subsituacao,
    c.situacao_publicacao,
    c.instrumento_ativo,
    c.ug_emitente::text as ug_emitente,

    -- Datas
    c.dia_assin_conv as data_assinatura,
    c.dia_publ_conv as data_publicacao,
    c.dia_inic_vigenc_conv as data_inicio_vigencia,
    c.dia_fim_vigenc_conv as data_fim_vigencia,
    c.dia_fim_vigenc_original_conv as data_fim_vigencia_original,
    c.dia_limite_prest_contas as data_limite_prestacao_contas,

    -- Valores pactuados
    c.valor_global_original_conv as valor_global_original,
    c.vl_global_conv as valor_global,
    c.vl_repasse_conv as valor_repasse,
    c.vl_contrapartida_conv as valor_contrapartida,
    c.vl_saldo_conta as valor_saldo_conta,

    -- Convenente e local de execucao
    regexp_replace(p.identif_proponente, '\D', '', 'g') as convenente_documento,
    p.nm_proponente as convenente_nome,
    p.natureza_juridica as convenente_natureza_juridica,
    p.uf_proponente as uf,
    p.munic_proponente as municipio,
    lpad(p.cod_munic_ibge::text, 7, '0') as cod_municipio_ibge,

    -- Origem do recurso
    case
        when o.tem_emenda
        then 'Emenda'
        when o.nr_convenio is not null
        then 'Recurso próprio'
        else 'Não identificada'
    end as origem_recurso,
    coalesce(o.tem_emenda and o.tem_proprio, false) as complemento_proprio,
    o.ug_responsavel_codigo,
    o.ug_responsavel_nome
from {{ ref("convenio") }} as c
inner join recorte as r on r.nr_convenio = c.nr_convenio
left join {{ ref("proposta") }} as p on p.id_proposta = c.id_proposta
left join origem as o on o.nr_convenio = c.nr_convenio
```

- [ ] **Step 4: Formatar, construir e testar**

Run (da raiz do repo): `/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad/sqlfmt-venv/bin/sqlfmt airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_mir.sql airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_recorte.sql airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_origem.sql`
Run (no projeto dbt): `dbt build --profiles-dir . --no-partial-parse -s convenio_mir`
Expected: `PASS=10 WARN=0 ERROR=0` (1 modelo + 7 genéricos + 2 singulares).

- [ ] **Step 5: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -c "select origem_recurso, count(*), count(*) filter (where complemento_proprio) compl from mir_silver.convenio_mir group by 1 order by 1" -c "select modalidade, count(*) from mir_silver.convenio_mir group by 1 order by 1"
```
Expected: `Emenda 189 2`, `Não identificada 418 0`, `Recurso próprio 36 0`; `CONVENIO 402`, `TERMO DE COLABORACAO 6`, `TERMO DE FOMENTO 234`, `TERMO DE PARCERIA 1`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P="airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_mir.sql airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_recorte.sql airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_mir_origem.sql"
git add $P
git commit -m "feat(dbt/mir): convenio_mir com recorte do MIR e origem do recurso" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 2: `convenio_movimento_financeiro` e `convenio_cronograma`

**Files:**
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_movimento_financeiro.sql`
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_cronograma.sql`
- Modify: `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` (acrescentar ao final)
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_movimento_reconciliacao.sql`
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_cronograma_reconciliacao.sql`

**Interfaces:**
- Consumes: `ref("convenio_mir")` (Task 1, `nr_convenio`); bronze `ref("desembolso")`, `ref("ingresso_contrapartida")`, `ref("desbloqueio")`, `ref("pagamento")`, `ref("pagamento_tributo")`, `ref("cronograma_desembolso")`.
- Produces:
  - `mir_silver.convenio_movimento_financeiro`: PK `id_movimento text`; `nr_convenio text`, `tipo_movimento text` (`Desembolso federal` | `Contrapartida depositada` | `Desbloqueio` | `Pagamento a fornecedor` | `Pagamento de tributo`), `data_movimento date` (nula em 28 tributos), `valor numeric`, `fornecedor_documento text` (só dígitos; só em pagamento), `fornecedor_nome text`, `documento_referencia text`.
  - `mir_silver.convenio_cronograma`: PK `id_parcela text`; `nr_convenio text`, `nr_parcela integer`, `responsavel text`, `data_prevista date` (1º dia do mês previsto), `valor_previsto numeric`.

- [ ] **Step 1: Escrever os testes singulares**

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_movimento_reconciliacao.sql`:

```sql
-- Falha se, para algum tipo de movimento, a quantidade ou a soma na silver
-- divergir da bronze correspondente restrita aos convenios do MIR.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    bronze as (
        select 'Desembolso federal' as tipo_movimento, count(*) as qtd, coalesce(sum(vl_desembolsado), 0) as valor
        from {{ ref("desembolso") }} where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Contrapartida depositada', count(*), coalesce(sum(vl_ingresso_contrapartida), 0)
        from {{ ref("ingresso_contrapartida") }} where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Desbloqueio', count(*), coalesce(sum(vl_desbloqueado), 0)
        from {{ ref("desbloqueio") }} where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Pagamento a fornecedor', count(*), coalesce(sum(vl_pago), 0)
        from {{ ref("pagamento") }} where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Pagamento de tributo', count(*), coalesce(sum(vl_pag_tributos), 0)
        from {{ ref("pagamento_tributo") }} where nr_convenio in (select nr_convenio from mir)
    ),

    silver as (
        select tipo_movimento, count(*) as qtd, coalesce(sum(valor), 0) as valor
        from {{ ref("convenio_movimento_financeiro") }}
        group by tipo_movimento
    )

select b.tipo_movimento, b.qtd as qtd_bronze, s.qtd as qtd_silver, b.valor as valor_bronze, s.valor as valor_silver
from bronze as b
left join silver as s on s.tipo_movimento = b.tipo_movimento
where coalesce(s.qtd, 0) <> b.qtd or coalesce(s.valor, 0) <> b.valor
```

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_cronograma_reconciliacao.sql`:

```sql
-- Falha se o cronograma da silver perder ou duplicar parcelas da bronze dos
-- convenios do MIR.
with
    bronze as (
        select count(*) as qtd, coalesce(sum(valor_parcela_crono_desembolso), 0) as valor
        from {{ ref("cronograma_desembolso") }}
        where nr_convenio in (select nr_convenio from {{ ref("convenio_mir") }})
    ),

    silver as (
        select count(*) as qtd, coalesce(sum(valor_previsto), 0) as valor
        from {{ ref("convenio_cronograma") }}
    )

select b.qtd as qtd_bronze, s.qtd as qtd_silver, b.valor as valor_bronze, s.valor as valor_silver
from bronze as b, silver as s
where b.qtd <> s.qtd or b.valor <> s.valor
```

Acrescentar ao final de `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml`:

```yaml
  - name: convenio_movimento_financeiro
    description: >
      Movimentos financeiros datados dos convenios do MIR, uma linha por
      movimento: desembolso federal, contrapartida depositada, desbloqueio,
      pagamento a fornecedor e pagamento de tributo.
    columns:
      - name: id_movimento
        description: "Chave do movimento: md5 do tipo, do convenio e da chave natural na origem."
        tests:
          - unique
          - not_null
      - name: nr_convenio
        description: "Convenio do movimento."
        tests:
          - not_null
          - relationships:
              to: ref('convenio_mir')
              field: nr_convenio
      - name: tipo_movimento
        description: "Tipo do movimento."
        tests:
          - not_null
          - accepted_values:
              values: ["Desembolso federal", "Contrapartida depositada", "Desbloqueio", "Pagamento a fornecedor", "Pagamento de tributo"]
      - name: data_movimento
        description: "Data do movimento. Nula em pagamentos de tributo sem data na origem."
      - name: valor
        description: "Valor do movimento."
        tests:
          - not_null
      - name: fornecedor_documento
        description: "CPF/CNPJ do fornecedor (so digitos). Preenchido so em pagamento a fornecedor."
      - name: documento_referencia
        description: "Documento de origem: numero SIAFI do desembolso, OB do desbloqueio ou DL do pagamento."

  - name: convenio_cronograma
    description: >
      Parcelas previstas no cronograma de desembolso dos convenios do MIR, uma
      linha por convenio x parcela x responsavel.
    columns:
      - name: id_parcela
        description: "Chave da parcela: md5 de convenio, numero da parcela e responsavel."
        tests:
          - unique
          - not_null
      - name: nr_convenio
        description: "Convenio da parcela."
        tests:
          - not_null
          - relationships:
              to: ref('convenio_mir')
              field: nr_convenio
      - name: responsavel
        description: "Responsavel pela parcela: Concedente, Convenente ou Rendimento de Aplicação."
        tests:
          - not_null
      - name: data_prevista
        description: "Primeiro dia do mes previsto para a parcela."
        tests:
          - not_null
      - name: valor_previsto
        description: "Valor previsto da parcela."
        tests:
          - not_null
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `dbt test --profiles-dir . --no-partial-parse -s convenio_movimento_reconciliacao`
Expected: erro de compilação `depends on a node named 'convenio_movimento_financeiro' which was not found`.

- [ ] **Step 3: Implementar os modelos**

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_movimento_financeiro.sql`:

```sql
{{ config(materialized="table") }}

-- Movimentos financeiros dos convenios do MIR, uma linha por movimento. Une as
-- tabelas do SICONV que tem a mesma forma (convenio, data, valor) para que o BI
-- compare entradas e saidas numa fato so. A chave de cada tipo e a chave
-- natural da origem (unica nos dados do MIR, garantida pelo teste unique).
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    movimentos as (
        select
            nr_convenio,
            'Desembolso federal' as tipo_movimento,
            id_desembolso::text as chave_origem,
            data_desembolso as data_movimento,
            vl_desembolsado as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            nr_siafi as documento_referencia
        from {{ ref("desembolso") }}

        union all

        select
            nr_convenio,
            'Contrapartida depositada' as tipo_movimento,
            concat_ws('|', dt_ingresso_contrapartida, vl_ingresso_contrapartida)
            as chave_origem,
            dt_ingresso_contrapartida as data_movimento,
            vl_ingresso_contrapartida as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as documento_referencia
        from {{ ref("ingresso_contrapartida") }}

        union all

        select
            nr_convenio,
            'Desbloqueio' as tipo_movimento,
            nr_ob as chave_origem,
            data_cadastro as data_movimento,
            vl_desbloqueado as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            nr_ob as documento_referencia
        from {{ ref("desbloqueio") }}

        union all

        select
            nr_convenio,
            'Pagamento a fornecedor' as tipo_movimento,
            nr_mov_fin::text as chave_origem,
            data_pag as data_movimento,
            vl_pago as valor,
            regexp_replace(identif_fornecedor, '\D', '', 'g') as fornecedor_documento,
            nome_fornecedor as fornecedor_nome,
            nr_dl as documento_referencia
        from {{ ref("pagamento") }}

        union all

        select
            nr_convenio,
            'Pagamento de tributo' as tipo_movimento,
            concat_ws('|', data_tributo, vl_pag_tributos) as chave_origem,
            data_tributo as data_movimento,
            vl_pag_tributos as valor,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as documento_referencia
        from {{ ref("pagamento_tributo") }}
    )

select
    md5(concat_ws('|', m.tipo_movimento, m.nr_convenio, m.chave_origem))
    as id_movimento,
    m.nr_convenio,
    m.tipo_movimento,
    m.data_movimento,
    m.valor,
    m.fornecedor_documento,
    m.fornecedor_nome,
    m.documento_referencia
from movimentos as m
inner join mir on mir.nr_convenio = m.nr_convenio
```

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_cronograma.sql`:

```sql
{{ config(materialized="table") }}

-- Cronograma de desembolso previsto dos convenios do MIR, uma linha por
-- convenio x parcela x responsavel. A data prevista e o primeiro dia do mes.
select
    md5(
        concat_ws(
            '|',
            c.nr_convenio,
            c.nr_parcela_crono_desembolso,
            c.tipo_resp_crono_desembolso
        )
    ) as id_parcela,
    c.nr_convenio,
    c.nr_parcela_crono_desembolso as nr_parcela,
    c.tipo_resp_crono_desembolso as responsavel,
    make_date(c.ano_crono_desembolso, c.mes_crono_desembolso, 1) as data_prevista,
    c.valor_parcela_crono_desembolso as valor_previsto
from {{ ref("cronograma_desembolso") }} as c
inner join {{ ref("convenio_mir") }} as mir on mir.nr_convenio = c.nr_convenio
```

- [ ] **Step 4: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt nos 2 modelos e 2 testes novos.
Run: `dbt build --profiles-dir . --no-partial-parse -s convenio_movimento_financeiro convenio_cronograma`
Expected: `PASS=18 WARN=0 ERROR=0` (2 modelos + 14 genéricos + 2 singulares).

- [ ] **Step 5: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -c "select tipo_movimento, count(*), round(sum(valor),2), count(*) filter (where data_movimento is null) sem_data from mir_silver.convenio_movimento_financeiro group by 1 order by 1" -c "select count(*), round(sum(valor_previsto),2) from mir_silver.convenio_cronograma"
```
Expected: `Contrapartida depositada 291 4599883.02 0`, `Desembolso federal 568 128160017.70 0`, `Pagamento a fornecedor 20911 100329484.72 0`, `Pagamento de tributo 668 797831.78 28`; cronograma `1177 176471172.94`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P="airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_movimento_financeiro.sql airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_cronograma.sql airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_movimento_reconciliacao.sql airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_cronograma_reconciliacao.sql"
git add $P
git commit -m "feat(dbt/mir): movimentos financeiros e cronograma dos convenios em mir_silver" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 3: `convenio_evento` e `convenio_contagens`

**Files:**
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_evento.sql`
- Create: `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_contagens.sql`
- Modify: `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml` (acrescentar ao final)
- Test: `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_evento_reconciliacao.sql`

**Interfaces:**
- Consumes: `ref("convenio_mir")`; bronze `ref("historico_situacao")`, `ref("termo_aditivo")`, `ref("prorroga_oficio")`, `ref("solicitacao_alteracao")`, `ref("solicitacao_rendimento_aplicacao")`, `ref("meta_crono_fisico")`, `ref("licitacao")`.
- Produces:
  - `mir_silver.convenio_evento`: PK `id_evento text`; `nr_convenio text`, `tipo_evento text` (`Mudança de situação` | `Termo aditivo` | `Prorrogação de ofício` | `Solicitação de alteração` | `Solicitação de rendimento`), `data_evento date`, `situacao text`, `descricao text`, `valor numeric`, `valor_aprovado numeric`, `dias integer`, `data_fim_nova date`.
  - `mir_silver.convenio_contagens`: PK `nr_convenio text` (uma linha para cada um dos 643 convênios); `qtd_metas bigint`, `valor_metas numeric`, `meta_expirada boolean`, `qtd_licitacoes bigint`, `valor_licitado numeric`.

- [ ] **Step 1: Escrever o teste singular**

Criar `airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_evento_reconciliacao.sql`:

```sql
-- Falha se a quantidade de eventos de algum tipo divergir da bronze dos
-- convenios do MIR depois das limpezas documentadas: historico de situacao
-- sem repeticoes (uma linha por convenio x data x situacao) e prorrogacoes
-- sem linhas identicas.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    bronze as (
        select 'Mudança de situação' as tipo_evento, count(*) as qtd
        from (
            select nr_convenio, dia_historico_sit, historico_sit, cod_historico_sit
            from {{ ref("historico_situacao") }}
            where nr_convenio in (select nr_convenio from mir)
            group by nr_convenio, dia_historico_sit, historico_sit, cod_historico_sit
        ) as h
        union all
        select 'Termo aditivo', count(*)
        from {{ ref("termo_aditivo") }} where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Prorrogação de ofício', count(*)
        from (
            select distinct *
            from {{ ref("prorroga_oficio") }}
            where nr_convenio in (select nr_convenio from mir)
        ) as p
        union all
        select 'Solicitação de alteração', count(*)
        from {{ ref("solicitacao_alteracao") }} where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Solicitação de rendimento', count(*)
        from {{ ref("solicitacao_rendimento_aplicacao") }} where nr_convenio in (select nr_convenio from mir)
    ),

    silver as (
        select tipo_evento, count(*) as qtd
        from {{ ref("convenio_evento") }}
        group by tipo_evento
    )

select b.tipo_evento, b.qtd as qtd_bronze, s.qtd as qtd_silver
from bronze as b
left join silver as s on s.tipo_evento = b.tipo_evento
where coalesce(s.qtd, 0) <> b.qtd
```

Acrescentar ao final de `airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml`:

```yaml
  - name: convenio_evento
    description: >
      Eventos administrativos datados dos convenios do MIR, uma linha por evento:
      mudanca de situacao, termo aditivo, prorrogacao de oficio, solicitacao de
      alteracao e solicitacao de uso de rendimento de aplicacao.
    columns:
      - name: id_evento
        description: "Chave do evento: md5 do tipo, do convenio e da chave natural na origem."
        tests:
          - unique
          - not_null
      - name: nr_convenio
        description: "Convenio do evento."
        tests:
          - not_null
          - relationships:
              to: ref('convenio_mir')
              field: nr_convenio
      - name: tipo_evento
        description: "Tipo do evento."
        tests:
          - not_null
          - accepted_values:
              values: ["Mudança de situação", "Termo aditivo", "Prorrogação de ofício", "Solicitação de alteração", "Solicitação de rendimento"]
      - name: data_evento
        description: "Data do evento (situacao, assinatura do aditivo ou da prorrogacao, ou da solicitacao)."
      - name: situacao
        description: "Situacao informada pelo evento (nova situacao do convenio, situacao da prorrogacao ou da solicitacao)."
      - name: valor
        description: "Valor global do aditivo ou valor solicitado de rendimento."
      - name: valor_aprovado
        description: "Valor aprovado da solicitacao de rendimento."
      - name: dias
        description: "Dias na situacao (mudanca de situacao) ou dias prorrogados."
      - name: data_fim_nova
        description: "Nova data de fim de vigencia (termo aditivo ou prorrogacao)."

  - name: convenio_contagens
    description: >
      Contagens de metas fisicas e licitacoes por convenio do MIR, uma linha por
      convenio (zero quando nao ha registro).
    columns:
      - name: nr_convenio
        description: "Convenio."
        tests:
          - unique
          - not_null
          - relationships:
              to: ref('convenio_mir')
              field: nr_convenio
      - name: meta_expirada
        description: "Verdadeiro se alguma meta tem data de fim anterior a data da execucao."
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `dbt test --profiles-dir . --no-partial-parse -s convenio_evento_reconciliacao`
Expected: erro de compilação `depends on a node named 'convenio_evento' which was not found`.

- [ ] **Step 3: Implementar os modelos**

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_evento.sql`:

```sql
{{ config(materialized="table") }}

-- Eventos administrativos dos convenios do MIR, uma linha por evento.
-- Limpezas da origem:
--   * historico_situacao traz linhas repetidas a cada ingestao, as vezes com
--     dias_historico_sit recalculado: fica uma linha por convenio x data x
--     situacao, com o maior numero de dias;
--   * prorroga_oficio traz linhas identicas e reuso de nr_prorroga para
--     prorrogacoes distintas: a chave inclui a data de inicio.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    historico as (
        select
            nr_convenio,
            dia_historico_sit,
            historico_sit,
            cod_historico_sit,
            max(dias_historico_sit) as dias_historico_sit
        from {{ ref("historico_situacao") }}
        group by nr_convenio, dia_historico_sit, historico_sit, cod_historico_sit
    ),

    prorrogacoes as (select distinct * from {{ ref("prorroga_oficio") }}),

    eventos as (
        select
            nr_convenio,
            'Mudança de situação' as tipo_evento,
            concat_ws('|', dia_historico_sit, cod_historico_sit, historico_sit)
            as chave_origem,
            dia_historico_sit as data_evento,
            historico_sit as situacao,
            null::text as descricao,
            null::numeric as valor,
            null::numeric as valor_aprovado,
            dias_historico_sit as dias,
            null::date as data_fim_nova
        from historico

        union all

        select
            nr_convenio,
            'Termo aditivo' as tipo_evento,
            numero_ta as chave_origem,
            dt_assinatura_ta as data_evento,
            null::text as situacao,
            tipo_ta as descricao,
            vl_global_ta as valor,
            null::numeric as valor_aprovado,
            null::integer as dias,
            dt_fim_ta as data_fim_nova
        from {{ ref("termo_aditivo") }}

        union all

        select
            nr_convenio,
            'Prorrogação de ofício' as tipo_evento,
            concat_ws('|', nr_prorroga, dt_inicio_prorroga) as chave_origem,
            dt_assinatura_prorroga as data_evento,
            sit_prorroga as situacao,
            null::text as descricao,
            null::numeric as valor,
            null::numeric as valor_aprovado,
            dias_prorroga as dias,
            dt_fim_prorroga as data_fim_nova
        from prorrogacoes

        union all

        select
            nr_convenio,
            'Solicitação de alteração' as tipo_evento,
            id_solicitacao::text as chave_origem,
            data_solicitacao as data_evento,
            situacao_solicitacao as situacao,
            objeto_solicitacao as descricao,
            null::numeric as valor,
            null::numeric as valor_aprovado,
            null::integer as dias,
            null::date as data_fim_nova
        from {{ ref("solicitacao_alteracao") }}

        union all

        select
            nr_convenio,
            'Solicitação de rendimento' as tipo_evento,
            id_solicitacao_rend_aplicacao::text as chave_origem,
            data_solicitacao_rend_aplicacao as data_evento,
            status_solicitacao_rend_aplicacao as situacao,
            null::text as descricao,
            valor_solicitacao_rend_aplicacao as valor,
            valor_aprovado_solicitacao_rend_aplicacao as valor_aprovado,
            null::integer as dias,
            null::date as data_fim_nova
        from {{ ref("solicitacao_rendimento_aplicacao") }}
    )

select
    md5(concat_ws('|', e.tipo_evento, e.nr_convenio, e.chave_origem)) as id_evento,
    e.nr_convenio,
    e.tipo_evento,
    e.data_evento,
    e.situacao,
    e.descricao,
    e.valor,
    e.valor_aprovado,
    e.dias,
    e.data_fim_nova
from eventos as e
inner join mir on mir.nr_convenio = e.nr_convenio
```

Criar `airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_contagens.sql`:

```sql
{{ config(materialized="table") }}

-- Contagens de metas fisicas e licitacoes por convenio do MIR. O gold atual so
-- usa esses dados como contagens; o detalhe por meta ou licitacao vira fato
-- propria quando algum painel precisar.
with
    metas as (
        select
            nr_convenio,
            count(*) as qtd_metas,
            sum(vl_meta) as valor_metas,
            bool_or(data_fim_meta < current_date) as meta_expirada
        from {{ ref("meta_crono_fisico") }}
        group by nr_convenio
    ),

    licitacoes as (
        select
            nr_convenio, count(*) as qtd_licitacoes, sum(valor_licitacao) as valor_licitado
        from {{ ref("licitacao") }}
        group by nr_convenio
    )

select
    c.nr_convenio,
    coalesce(m.qtd_metas, 0) as qtd_metas,
    coalesce(m.valor_metas, 0) as valor_metas,
    coalesce(m.meta_expirada, false) as meta_expirada,
    coalesce(l.qtd_licitacoes, 0) as qtd_licitacoes,
    coalesce(l.valor_licitado, 0) as valor_licitado
from {{ ref("convenio_mir") }} as c
left join metas as m on m.nr_convenio = c.nr_convenio
left join licitacoes as l on l.nr_convenio = c.nr_convenio
```

- [ ] **Step 4: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt nos 2 modelos e no teste novo.
Run: `dbt build --profiles-dir . --no-partial-parse -s convenio_evento convenio_contagens`
Expected: `PASS=12 WARN=0 ERROR=0` (2 modelos + 9 genéricos + 1 singular).

- [ ] **Step 5: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -c "select tipo_evento, count(*) from mir_silver.convenio_evento group by 1 order by 1" -c "select count(*), sum(qtd_metas), round(sum(valor_metas),2), sum(qtd_licitacoes), round(sum(valor_licitado),2) from mir_silver.convenio_contagens"
```
Expected: `Mudança de situação 14358`, `Prorrogação de ofício 209`, `Solicitação de alteração 747`, `Solicitação de rendimento 121`, `Termo aditivo 468`; contagens `643 | 1648 | 177994936.13 | 6563 | 229504133.73`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P="airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_evento.sql airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_contagens.sql airflow_lappis/dags/dbt/mir/models/mir_silver/schema.yml airflow_lappis/dags/dbt/mir/tests/mir_silver/convenio_evento_reconciliacao.sql"
git add $P
git commit -m "feat(dbt/mir): eventos administrativos e contagens dos convenios em mir_silver" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 4: Verificação final da etapa 2a

**Files:** nenhum arquivo novo.

- [ ] **Step 1: Construir tudo de `mir_silver`**

Run: `dbt build --profiles-dir . --no-partial-parse -s path:models/mir_silver`
Expected: `PASS=72 WARN=0 ERROR=0` (32 da etapa 1 + 10 + 18 + 12).

- [ ] **Step 2: Confirmar que nenhum modelo fora de `mir_silver` mudou nesta etapa**

Run (da raiz): `git diff 5d83f0f --stat -- airflow_lappis/dags/dbt/mir/models ':!airflow_lappis/dags/dbt/mir/models/mir_silver'`
Expected: saída vazia.

- [ ] **Step 3: Lint**

Run (da raiz): sqlfmt `--check` em `airflow_lappis/dags/dbt/mir/models/mir_silver airflow_lappis/dags/dbt/mir/tests/mir_silver`
Expected: todos passam.

## Fora desta etapa

- Etapa 2b: macros (`surrogate_key`, membro `-1`, geradores das dimensões compartilhadas), seed UF → região, dimensões e fatos de `mir_convenios`, posição por convênio e paridade com `resumo_convenios` / `resumo_termos_fomento` (comparação por convênio: o gold atual tem 834 linhas para 643 convênios).
- As flags inadimplente/rescindido/anulado da `dim_convenio` saem de `convenio_evento` na etapa 2b.
