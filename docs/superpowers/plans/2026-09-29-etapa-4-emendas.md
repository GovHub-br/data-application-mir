# Etapa 4: Mart de Emendas (`mir_emendas`) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o data mart `mir_emendas` (emenda, parlamentar, instrumento executor, favorecido, localizador, execução, dotação e posição por emenda) para o Power BI de Emendas, com as dimensões compartilhadas passando a cobrir também os códigos que só aparecem na dotação, e o teste de consistência entre os três marts.

**Architecture:** A emenda é a origem do recurso; o instrumento é registrado na NE (`execucao_ne.sistema_instrumento`/`nr_instrumento`). A dotação (`tg_emendas_dotacao`) é um livro de movimentos diários (lançamentos positivos e negativos) e vira a silver `emenda_dotacao`. O parlamentar de cada NE e de cada movimento de dotação é achado na data do evento por uma macro única (`parlamentar_na_data`), extraída de `emenda_ne`.

**Tech Stack:** dbt-core/dbt-postgres 1.7.13, PostgreSQL 17 (container `mir-dump-pg17`, porta 5433, database `analytics`), shandy-sqlfmt 0.32.0.

**Spec:** `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§4, §5, §8, §11).

## Global Constraints

- Silver em `models/mir_silver/`; gold em `models/mir_emendas/`, schema `mir_emendas`, materialização `table` (configurado na Tarefa 5).
- Todo modelo de `models/mir_emendas/` tem o prefixo `emendas_` no nome do arquivo e `{{ config(alias="<nome sem prefixo>") }}` (nomes de modelo do dbt são únicos no projeto). Os `ref()` usam o nome com prefixo.
- Nenhum modelo fora de `mir_silver`, `mir_emendas` e das macros de `macros/mir_gold/` muda. As mudanças nas macros de dimensão (Tarefa 4) acrescentam membros às dimensões de `mir_convenios` e `mir_teds`, sem mudar os membros existentes.
- `emenda_ne` é refatorado para usar a macro `parlamentar_na_data`, com **saída idêntica** nas colunas existentes (conferida por md5).
- Instrumento executor (spec §8): `Convênio` · `Fomento` · `Colaboração` · `Parceria` (modalidade de `convenio_mir`), `TED`, `Convênio de outro órgão` (SICONV fora de `convenio_mir`, decisão do usuário em 2026-09-29) e `-1` = `Execução direta / não identificado`.
- Chaves do gold: `surrogate_key`, `fk` (−1 quando a primeira coluna é nula), `sk_tempo`. Toda dimensão tem o membro `-1`.
- RAP somável entre exercícios exclui `reinscricao_rap = true`.
- Literais de dados levam acento; comentários SQL em português sem acentos.
- Todo `.sql` novo ou alterado passa pelo sqlfmt antes do commit.
- Commits só com os arquivos da tarefa (`git add -- <paths>` e `git commit ... -- <paths>`); há ~90 arquivos de `dicionario-mir/` em stage que não podem ser commitados, retirados do stage nem resetados. Mensagem: assunto e, num segundo `-m`, só `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Nunca rodar `dbt build/run` sem `-s`, nunca usar operadores `+`, nunca `--full-refresh`.

### Ambiente local

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
export DB_DW_HOST_MIR=localhost DB_DW_PORT_MIR=5433 DB_DW_USER_MIR=postgres \
       DB_DW_PASSWORD_MIR=postgres DB_DW_DBNAME_MIR=analytics DB_DW_SCHEMA_MIR=mir
```

- dbt: `poetry run dbt <cmd> --profiles-dir . --no-partial-parse ...`.
- sqlfmt, da raiz do repositório: `/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad/sqlfmt-venv/bin/sqlfmt <arquivos>`.
- Consultas: `docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "<sql>"`.

### Linha de base medida em 2026-09-29 (dump local)

| Objeto | Esperado |
|---|---|
| NEs de emenda no núcleo | 221 NEs, 651 linhas; empenhado 55.822.240,37 · liquidado 23.534.892,51 · pago 22.537.602,51 · RAP inscrito sem reinscrição 23.136.594,77 · RAP pago 19.760.949,24 (iguais ao `tg_emendas`, linha a linha) |
| Instrumento das NEs de emenda | SICONV do MIR 207 NEs (51.672.240,37) · SICONV de outro órgão 3 (900.000,00) · TED 4 (1.650.000,00) · Não identificado 7 (1.600.000,00) |
| `emenda_dotacao` | 1.058 movimentos; dotação inicial 65.121.784,00 · atualizada 63.829.841,00; 92 emendas; parlamentar prioridade 1 = 1.012, 3 = 46 |
| `emenda_instrumento` | 195 instrumentos: Fomento 162 · Convênio 27 · TED 4 · Convênio de outro órgão 2 |
| Dotação sem NE | 6 emendas, 8 PTRES e 11 naturezas só aparecem na dotação |
| Favorecidos das NEs de emenda | 142 CNPJs (nenhum CPF hoje) |
| Localizadores | 1 por NE; 36 na dotação |

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `macros/mir_silver/parlamentar_na_data.sql` | Create | parlamentar autor na data (regra de `emenda_ne`) |
| `models/mir_silver/emenda_ne.sql` | Modify | usa a macro; ganha o localizador da NE |
| `models/mir_silver/emenda_dotacao.sql` | Create | movimentos de dotação com parlamentar |
| `models/mir_silver/emenda_instrumento.sql` | Create | instrumentos executores das NEs de emenda |
| `models/mir_silver/schema.yml`, `tests/mir_silver/emenda_*.sql` | Modify / Create | documentação e testes |
| `macros/mir_gold/dim_emenda.sql`, `dim_acao_orcamentaria.sql`, `dim_natureza_despesa.sql`, `dim_fonte_recurso.sql` | Modify | também leem a dotação |
| `dbt_project.yml` | Modify | schema `mir_emendas` |
| `models/mir_emendas/emendas_*.sql`, `schema.yml` | Create | o mart |
| `tests/mir_emendas/*.sql` | Create | reconciliação, posição e consistência entre marts |
| `analyses/paridade_mir_emendas.sql` | Create | paridade temporária com o gold antigo (apagar na etapa 5) |

Caminhos relativos a `airflow_lappis/dags/dbt/mir/`, exceto os de `docs/`.

---

### Task 1: Macro `parlamentar_na_data` e localizador em `emenda_ne`

**Files:**
- Create: `macros/mir_silver/parlamentar_na_data.sql`
- Modify: `models/mir_silver/emenda_ne.sql` (conteúdo completo abaixo)
- Modify: `models/mir_silver/schema.yml` (colunas novas de `emenda_ne`)

**Interfaces:**
- Produces: `{{ parlamentar_na_data("<cte>") }}` — a CTE tem `chave`, `autor_nome`, `data_referencia date`; devolve uma linha por `chave` com `id_parlamentar`, `cargo_parlamentar`, `sigla_partido`, `prioridade_match`. `emenda_ne` ganha `localizador_gasto`, `localizador_descricao`, `regiao`, `uf`, `uf_nome`.

- [ ] **Step 1: Registrar a linha de base de `emenda_ne`**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "select count(*), md5(string_agg(concat_ws('|', ne_ccor, codigo_emenda, emenda_descricao, autor_nome, data_emissao_ne, id_parlamentar, cargo_parlamentar, sigla_partido, prioridade_match), ',' order by ne_ccor)) from mir_silver.emenda_ne"
```
Guardar a saída (esperado `221|<md5>`).

- [ ] **Step 2: Criar `macros/mir_silver/parlamentar_na_data.sql`**

```sql
{#
    Parlamentar autor de uma emenda numa data. Acha o parlamentar pelo nome em
    parlamentares_historico, com as prioridades do emendas_partidos:
    1 = filiacao vigente na data; 2 = nome encontrado, mas nenhuma filiacao
    cobre a data (fica a mais proxima); 3 = nome nao encontrado (parlamentar
    nulo). Filiacao sem data de fim vale como aberta (infinity), sem depender
    da data de hoje.
    origem: nome de uma CTE com as colunas chave, autor_nome e data_referencia.
    Devolve uma linha por chave: chave, id_parlamentar, cargo_parlamentar,
    sigla_partido, prioridade_match.
#}
{% macro parlamentar_na_data(origem) %}
    select distinct on (o.chave)
        o.chave,
        p.id_parlamentar,
        p.cargo_parlamentar,
        p.sigla_partido,
        case
            when p.id_parlamentar is null
            then 3
            when
                o.data_referencia >= p.data_filiacao::date
                and o.data_referencia
                <= coalesce(p.data_desfiliacao::date, 'infinity'::date)
            then 1
            else 2
        end as prioridade_match
    from {{ origem }} as o
    left join
        {{ ref("parlamentares_historico") }} as p
        on p.chave_join_nome = {{ name_formater("o.autor_nome") }}
    order by
        o.chave,
        prioridade_match,
        least(
            abs(o.data_referencia - p.data_filiacao::date),
            abs(o.data_referencia - p.data_desfiliacao::date)
        ) nulls last,
        p.id_parlamentar,
        p.sigla_partido
{% endmacro %}
```

- [ ] **Step 3: Reescrever `models/mir_silver/emenda_ne.sql`**

```sql
{{ config(materialized="table") }}

-- NEs de emenda, uma linha por NE: a emenda (tg_emendas), o localizador do
-- gasto e o parlamentar autor com o partido vigente na data de emissao da NE
-- (regra na macro parlamentar_na_data).
with
    nes as (
        select
            ne_ccor,
            max(codigo_emenda) as codigo_emenda,
            -- A emissao da NE e a primeira data que nao e inscricao de RAP; NE
            -- so com linhas de RAP usa a primeira inscricao
            coalesce(
                min(data_emissao) filter (where not inscricao_rap), min(data_emissao)
            ) as data_emissao_ne
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
        group by ne_ccor
    ),

    -- Cada NE tem um autor e um localizador no tg_emendas
    autores as (
        select distinct on (ne_ccor)
            ne_ccor,
            autor_emendas_orcamento_descricao as emenda_descricao,
            autor_emendas_orcamento_nome as autor_nome,
            localizador_gasto,
            localizador_gasto_descricao as localizador_descricao,
            regiao_pt as regiao,
            uf_pt as uf,
            uf_pt_descricao as uf_nome
        from {{ ref("tg_emendas") }}
        order by ne_ccor, autor_emendas_orcamento_descricao
    ),

    origem as (
        select n.ne_ccor as chave, a.autor_nome, n.data_emissao_ne as data_referencia
        from nes as n
        inner join autores as a on a.ne_ccor = n.ne_ccor
    ),

    parlamentar as ({{ parlamentar_na_data("origem") }})

select
    n.ne_ccor,
    n.codigo_emenda,
    a.emenda_descricao,
    a.autor_nome,
    n.data_emissao_ne,
    p.id_parlamentar,
    p.cargo_parlamentar,
    p.sigla_partido,
    p.prioridade_match,
    a.localizador_gasto,
    a.localizador_descricao,
    a.regiao,
    a.uf,
    a.uf_nome
from nes as n
inner join autores as a on a.ne_ccor = n.ne_ccor
inner join parlamentar as p on p.chave = n.ne_ccor
```

- [ ] **Step 4: Documentar as colunas novas em `models/mir_silver/schema.yml`**

No modelo `emenda_ne`, acrescentar ao final das colunas:

```yaml
      - name: localizador_gasto
        description: "Localizador do gasto da NE (tg_emendas); um por NE."
        tests:
          - not_null
      - name: localizador_descricao
        description: "Descricao do localizador."
      - name: regiao
        description: "Regiao do localizador (ou NACIONAL)."
      - name: uf
        description: "UF do localizador (ou NACIONAL)."
      - name: uf_nome
        description: "Nome da UF do localizador."
```

- [ ] **Step 5: Formatar, construir e conferir**

Run (da raiz): sqlfmt na macro e no modelo.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s emenda_ne`
Expected: `ERROR=0` e `WARN=0`.
Run a consulta do Step 1. Expected: exatamente a mesma saída.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/macros/mir_silver/parlamentar_na_data.sql $M/models/mir_silver/emenda_ne.sql $M/models/mir_silver/schema.yml"
git add -- $P
git commit -m "refactor(dbt/mir): parlamentar na data em macro e localizador em emenda_ne" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 2: Silver — dotação e instrumento executor das emendas

**Files:**
- Create: `models/mir_silver/emenda_dotacao.sql`, `models/mir_silver/emenda_instrumento.sql`
- Modify: `models/mir_silver/schema.yml` (acrescentar ao final)
- Test: `tests/mir_silver/emenda_dotacao_reconciliacao.sql`
- Test: `tests/mir_silver/emenda_instrumento_cobertura.sql`
- Test: `tests/mir_silver/emenda_instrumento_chave_unica.sql`

**Interfaces:**
- Consumes: `ref("tg_emendas_dotacao")`, macro `parlamentar_na_data`; `ref("execucao_ne")`, `ref("convenio_mir")`, `ref("convenio")`, `ref("proposta")`, `ref("ted_plano_acao")`.
- Produces:
  - `mir_silver.emenda_dotacao`, PK `id_movimento`. Colunas: `codigo_emenda`, `emenda_descricao`, `autor_nome`, `data_movimento date`, `programa_governo text` (4 dígitos), `programa_governo_descricao`, `acao_governo`, `acao_governo_descricao`, `ptres text`, `natureza_despesa`, `natureza_despesa_descricao`, `grupo_despesa integer`, `grupo_despesa_descricao`, `modalidade_aplicacao integer`, `fonte_recursos_detalhada`, `fonte_recursos_detalhada_descricao`, `localizador_gasto`, `localizador_descricao`, `regiao`, `uf`, `uf_nome`, `dotacao_inicial`, `dotacao_atualizada`, `id_parlamentar`, `cargo_parlamentar`, `sigla_partido`, `prioridade_match`.
  - `mir_silver.emenda_instrumento`, PK (`sistema_instrumento`, `nr_instrumento`). Colunas: `tipo_instrumento`, `objeto`, `situacao`, `executor_nome`.

A dotação é um livro de movimentos (lançamentos positivos e negativos por dia), somável. Linhas idênticas no mesmo dia são movimentos distintos: a chave inclui um sequencial entre as idênticas.

- [ ] **Step 1: Escrever os testes singulares**

`tests/mir_silver/emenda_dotacao_reconciliacao.sql`:

```sql
-- Falha se emenda_dotacao perder ou duplicar movimentos ou valor da dotacao do
-- Tesouro.
with
    silver as (
        select
            count(*) as linhas,
            sum(dotacao_inicial) as inicial,
            sum(dotacao_atualizada) as atualizada
        from {{ ref("emenda_dotacao") }}
    ),

    bronze as (
        select
            count(*) as linhas,
            sum(dotacao_inicial) as inicial,
            sum(dotacao_atualizada) as atualizada
        from {{ ref("tg_emendas_dotacao") }}
    )

select s.*, b.linhas as linhas_bronze
from silver as s
cross join bronze as b
where
    s.linhas <> b.linhas
    or s.inicial <> b.inicial
    or s.atualizada <> b.atualizada
```

`tests/mir_silver/emenda_instrumento_cobertura.sql`:

```sql
-- Falha se algum instrumento de NE de emenda (fora os nao identificados) faltar
-- em emenda_instrumento ou ficar sem tipo.
select distinct x.sistema_instrumento, x.nr_instrumento
from {{ ref("execucao_ne") }} as x
left join
    {{ ref("emenda_instrumento") }} as i
    on i.sistema_instrumento = x.sistema_instrumento
    and i.nr_instrumento = x.nr_instrumento
where
    x.codigo_emenda is not null
    and x.sistema_instrumento <> 'Não identificado'
    and i.tipo_instrumento is null
```

- [ ] **Step 2: Criar `models/mir_silver/emenda_dotacao.sql`**

```sql
{{ config(materialized="table") }}

-- Dotacao das emendas do MIR, uma linha por movimento do relatorio do Tesouro
-- (lancamentos positivos e negativos por dia; a soma e a dotacao do periodo).
-- Linhas identicas no mesmo dia sao movimentos distintos: a chave leva um
-- sequencial entre elas. O parlamentar e o autor com o partido vigente na data
-- do movimento (macro parlamentar_na_data, mesma regra das NEs).
with
    base as (
        select
            d.*,
            row_number() over (
                partition by
                    d.autor_emendas_orcamento,
                    d.emissao_dia,
                    d.programa_governo,
                    d.acao_governo,
                    d.ptres,
                    d.natureza_despesa,
                    d.modalidade_aplicacao,
                    d.fonte_recursos_detalhada,
                    d.localizador_gasto,
                    d.dotacao_inicial,
                    d.dotacao_atualizada
                order by d.dt_ingest
            ) as sequencial
        from {{ ref("tg_emendas_dotacao") }} as d
    ),

    movimentos as (
        select
            md5(
                concat_ws(
                    '|',
                    autor_emendas_orcamento,
                    emissao_dia,
                    programa_governo,
                    acao_governo,
                    ptres,
                    natureza_despesa,
                    modalidade_aplicacao,
                    fonte_recursos_detalhada,
                    localizador_gasto,
                    dotacao_inicial,
                    dotacao_atualizada,
                    sequencial
                )
            ) as id_movimento,
            base.*
        from base
    ),

    origem as (
        select
            id_movimento as chave,
            autor_emendas_orcamento_nome as autor_nome,
            emissao_dia as data_referencia
        from movimentos
    ),

    parlamentar as ({{ parlamentar_na_data("origem") }})

select
    m.id_movimento,
    m.autor_emendas_orcamento as codigo_emenda,
    m.autor_emendas_orcamento_descricao as emenda_descricao,
    m.autor_emendas_orcamento_nome as autor_nome,
    m.emissao_dia as data_movimento,
    lpad(m.programa_governo::text, 4, '0') as programa_governo,
    m.programa_governo_descricao,
    m.acao_governo,
    m.acao_governo_descricao,
    m.ptres::text as ptres,
    m.natureza_despesa,
    m.natureza_despesa_descricao,
    m.grupo_despesa,
    m.grupo_despesa_descricao,
    m.modalidade_aplicacao,
    m.fonte_recursos_detalhada,
    m.fonte_recursos_detalhada_descricao,
    m.localizador_gasto,
    m.localizador_gasto_descricao as localizador_descricao,
    m.regiao_pt as regiao,
    m.uf_pt as uf,
    m.uf_pt_descricao as uf_nome,
    m.dotacao_inicial,
    m.dotacao_atualizada,
    p.id_parlamentar,
    p.cargo_parlamentar,
    p.sigla_partido,
    p.prioridade_match
from movimentos as m
inner join parlamentar as p on p.chave = m.id_movimento
```

- [ ] **Step 3: Criar `models/mir_silver/emenda_instrumento.sql`**

```sql
{{ config(materialized="table") }}

-- Instrumentos que executam as emendas do MIR, uma linha por instrumento
-- registrado nas NEs de emenda do nucleo. Tipo pela modalidade do convenio do
-- MIR, TED pelo plano de acao, e "Convênio de outro órgão" para convenio do
-- SICONV fora do universo convenio_mir (NE do relatorio do MIR emitida por
-- outra UG; decisao do usuario em 2026-09-29). NEs sem instrumento ficam de
-- fora: no gold apontam para o membro -1 (Execucao direta / nao identificado).
with
    instrumentos as (
        select distinct sistema_instrumento, nr_instrumento
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null and sistema_instrumento <> 'Não identificado'
    ),

    outros_orgaos as (
        select
            c.nr_convenio,
            c.sit_convenio as situacao,
            p.objeto_proposta as objeto,
            p.nm_proponente as executor_nome
        from {{ ref("convenio") }} as c
        left join {{ ref("proposta") }} as p on p.id_proposta = c.id_proposta
        where
            c.nr_convenio in (
                select nr_instrumento
                from instrumentos
                where sistema_instrumento = 'SICONV'
            )
    )

select
    i.sistema_instrumento,
    i.nr_instrumento,
    case
        when i.sistema_instrumento = 'TED'
        then 'TED'
        when m.nr_convenio is null
        then 'Convênio de outro órgão'
        when m.modalidade = 'CONVENIO'
        then 'Convênio'
        when m.modalidade = 'TERMO DE FOMENTO'
        then 'Fomento'
        when m.modalidade = 'TERMO DE COLABORACAO'
        then 'Colaboração'
        when m.modalidade = 'TERMO DE PARCERIA'
        then 'Parceria'
    end as tipo_instrumento,
    coalesce(m.objeto, o.objeto, t.objeto) as objeto,
    coalesce(m.situacao, o.situacao, t.situacao) as situacao,
    coalesce(m.convenente_nome, o.executor_nome, t.unidade_descentralizada) as executor_nome
from instrumentos as i
left join
    {{ ref("convenio_mir") }} as m
    on i.sistema_instrumento = 'SICONV'
    and m.nr_convenio = i.nr_instrumento
left join
    outros_orgaos as o
    on i.sistema_instrumento = 'SICONV'
    and m.nr_convenio is null
    and o.nr_convenio = i.nr_instrumento
left join
    {{ ref("ted_plano_acao") }} as t
    on i.sistema_instrumento = 'TED'
    and t.id_plano_acao::text = i.nr_instrumento
```

- [ ] **Step 4: Documentar em `models/mir_silver/schema.yml` (acrescentar ao final)**

```yaml
  - name: emenda_dotacao
    description: >
      Dotacao das emendas, uma linha por movimento do relatorio do Tesouro
      (lancamentos positivos e negativos; a soma e a dotacao do periodo), com o
      parlamentar autor vigente na data do movimento.
    columns:
      - name: id_movimento
        tests:
          - unique
          - not_null
      - name: codigo_emenda
        tests:
          - not_null
      - name: data_movimento
        tests:
          - not_null
      - name: prioridade_match
        tests:
          - not_null
          - accepted_values:
              values: [1, 2, 3]
              quote: false

  - name: emenda_instrumento
    description: >
      Instrumentos que executam as emendas (registrados nas NEs de emenda):
      tipo (Convênio, Fomento, Colaboração, Parceria, TED, Convênio de outro
      órgão), objeto, situacao e executor.
    columns:
      - name: tipo_instrumento
        tests:
          - not_null
          - accepted_values:
              values: ["Convênio", "Fomento", "Colaboração", "Parceria", "TED", "Convênio de outro órgão"]
```

O projeto não usa o pacote `dbt_utils`; a chave composta é garantida pelo teste singular `tests/mir_silver/emenda_instrumento_chave_unica.sql`:

```sql
-- Falha se um instrumento aparecer mais de uma vez em emenda_instrumento.
select sistema_instrumento, nr_instrumento, count(*) as qtd
from {{ ref("emenda_instrumento") }}
group by sistema_instrumento, nr_instrumento
having count(*) > 1
```

- [ ] **Step 5: Formatar, construir e conferir**

Run (da raiz): sqlfmt nos 2 modelos e nos testes.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s emenda_dotacao emenda_instrumento`
Expected: `ERROR=0` e `WARN=0`.

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At \
 -c "select count(*), count(distinct codigo_emenda), sum(dotacao_inicial), sum(dotacao_atualizada) from mir_silver.emenda_dotacao" \
 -c "select prioridade_match, count(*) from mir_silver.emenda_dotacao group by 1 order by 1" \
 -c "select tipo_instrumento, count(*) from mir_silver.emenda_instrumento group by 1 order by 1"
```
Expected: `1058|92|65121784.00|63829841.00`; `1|1012`, `3|46`; `Convênio|27`, `Convênio de outro órgão|2`, `Fomento|162`, `TED|4`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/models/mir_silver/emenda_dotacao.sql $M/models/mir_silver/emenda_instrumento.sql $M/models/mir_silver/schema.yml $M/tests/mir_silver/emenda_dotacao_reconciliacao.sql $M/tests/mir_silver/emenda_instrumento_cobertura.sql $M/tests/mir_silver/emenda_instrumento_chave_unica.sql"
git add -- $P
git commit -m "feat(dbt/mir): dotacao e instrumentos executores das emendas em mir_silver" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 3: Dimensões compartilhadas também leem a dotação

**Files:**
- Modify: `macros/mir_gold/dim_emenda.sql`, `macros/mir_gold/dim_acao_orcamentaria.sql`, `macros/mir_gold/dim_natureza_despesa.sql`, `macros/mir_gold/dim_fonte_recurso.sql` (conteúdo completo abaixo)

**Interfaces:**
- Consumes: `ref("emenda_dotacao")` (Tarefa 2), além das fontes atuais.
- Produces: as mesmas colunas de antes. Os membros que já existiam não mudam (a NE continua tendo prioridade sobre a dotação na escolha dos atributos); entram os códigos que só aparecem na dotação. Afeta também `mir_convenios` e `mir_teds`, que usam as mesmas macros.

Por quê: a `fato_dotacao` de Emendas tem 6 emendas, 8 PTRES e 11 naturezas que nenhuma NE usa. Sem eles na dimensão, a FK falharia no `relationships`, e mandar para `-1` esconderia justamente as emendas com dotação e sem empenho.

- [ ] **Step 1: Registrar a linha de base das dimensões de `mir_convenios`**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "
select 'emenda', count(*), md5(string_agg(t::text, ',' order by sk_emenda)) from mir_convenios.dim_emenda t union all
select 'acao', count(*), md5(string_agg(t::text, ',' order by sk_acao_orcamentaria)) from mir_convenios.dim_acao_orcamentaria t union all
select 'natureza', count(*), md5(string_agg(t::text, ',' order by sk_natureza_despesa)) from mir_convenios.dim_natureza_despesa t union all
select 'fonte', count(*), md5(string_agg(t::text, ',' order by sk_fonte_recurso)) from mir_convenios.dim_fonte_recurso t"
```
Guardar a saída (esperado `emenda|87`, `acao|143`, `natureza|40`, `fonte|34`).

- [ ] **Step 2: Reescrever as quatro macros**

`macros/mir_gold/dim_emenda.sql`:

```sql
{#
    Emenda parlamentar. O codigo tem 12 digitos: ano (4) + autor (4) + numero
    (4), ex.: 202443740013 = emenda 13 de 2024. Le as emendas com NE e as que so
    tem dotacao; com NE, os atributos vem da NE (primeira pelo ne_ccor).
#}
{% macro dim_emenda() %}
    select
        {{ surrogate_key(["codigo_emenda"]) }} as sk_emenda,
        codigo_emenda,
        left(codigo_emenda, 4)::integer as ano,
        right(codigo_emenda, 4)::integer as numero,
        emenda_descricao,
        autor_nome
    from
        (
            select distinct on (codigo_emenda) codigo_emenda, emenda_descricao, autor_nome
            from
                (
                    select
                        codigo_emenda,
                        emenda_descricao,
                        autor_nome,
                        1 as origem,
                        ne_ccor as desempate
                    from {{ ref("emenda_ne") }}

                    union all

                    select
                        codigo_emenda,
                        emenda_descricao,
                        autor_nome,
                        2 as origem,
                        id_movimento as desempate
                    from {{ ref("emenda_dotacao") }}
                ) as fontes
            order by codigo_emenda, origem, desempate
        ) as e

    union all

    select -1::bigint, '-1', null, null, 'Não identificado', 'Não identificado'
{% endmacro %}
```

`macros/mir_gold/dim_acao_orcamentaria.sql`:

```sql
{#
    Classificacao programatica no grao do PTRES: programa, acao, plano
    orcamentario, funcao e subfuncao (so os codigos de funcao e subfuncao; a
    origem nao traz os nomes). Le os PTRES das NEs e os que so aparecem na
    dotacao das emendas (esses sem plano orcamentario, funcao e subfuncao).
#}
{% macro dim_acao_orcamentaria() %}
    select
        {{ surrogate_key(["ptres"]) }} as sk_acao_orcamentaria,
        ptres,
        codigo_programa,
        programa,
        codigo_acao,
        acao,
        codigo_plano_orcamentario,
        plano_orcamentario,
        codigo_funcao,
        codigo_subfuncao,
        codigo_uo
    from
        (
            select distinct on (ptres) *
            from
                (
                    select
                        ptres,
                        programa_governo as codigo_programa,
                        programa_governo_descricao as programa,
                        acao_governo as codigo_acao,
                        acao_governo_descricao as acao,
                        plano_orcamentario_codigo_po as codigo_plano_orcamentario,
                        plano_orcamentario_nome as plano_orcamentario,
                        plano_orcamentario_codigo_funcao as codigo_funcao,
                        plano_orcamentario_codigo_subfuncao as codigo_subfuncao,
                        plano_orcamentario_codigo_uo as codigo_uo,
                        1 as origem,
                        dt_ingest
                    from {{ ref("execucao_ne") }}

                    union all

                    select
                        ptres,
                        programa_governo,
                        programa_governo_descricao,
                        acao_governo,
                        acao_governo_descricao,
                        null,
                        null,
                        null,
                        null,
                        null,
                        2,
                        null
                    from {{ ref("emenda_dotacao") }}
                ) as fontes
            order by ptres, origem, dt_ingest desc
        ) as a

    union all

    select
        -1::bigint,
        '-1',
        null,
        'Não identificado',
        null,
        'Não identificado',
        null,
        'Não identificado',
        null,
        null,
        null
{% endmacro %}
```

`macros/mir_gold/dim_natureza_despesa.sql`:

```sql
{#
    Natureza de despesa (6 digitos: categoria, GND, modalidade de aplicacao,
    elemento). A modalidade de aplicacao sai dos digitos 3 e 4. Le as naturezas
    das NEs e as que so aparecem na dotacao das emendas.
#}
{% macro dim_natureza_despesa() %}
    select
        {{ surrogate_key(["natureza_despesa"]) }} as sk_natureza_despesa,
        natureza_despesa,
        natureza_despesa_descricao,
        codigo_gnd,
        gnd,
        substr(natureza_despesa, 3, 2) as codigo_modalidade_aplicacao
    from
        (
            select distinct on (natureza_despesa) *
            from
                (
                    select
                        natureza_despesa,
                        natureza_despesa_descricao,
                        grupo_despesa as codigo_gnd,
                        grupo_despesa_desc as gnd,
                        1 as origem,
                        dt_ingest
                    from {{ ref("execucao_ne") }}

                    union all

                    select
                        natureza_despesa,
                        natureza_despesa_descricao,
                        grupo_despesa,
                        grupo_despesa_descricao,
                        2,
                        null
                    from {{ ref("emenda_dotacao") }}
                ) as fontes
            order by natureza_despesa, origem, dt_ingest desc
        ) as n

    union all

    select -1::bigint, '-1', 'Não identificado', null, 'Não identificado', null
{% endmacro %}
```

`macros/mir_gold/dim_fonte_recurso.sql`:

```sql
{#
    Fonte de recursos detalhada das NEs e da dotacao das emendas.
#}
{% macro dim_fonte_recurso() %}
    select {{ surrogate_key(["codigo_fonte"]) }} as sk_fonte_recurso, codigo_fonte, fonte
    from
        (
            select distinct on (codigo_fonte) *
            from
                (
                    select
                        fonte_recursos_detalhada as codigo_fonte,
                        fonte_recursos_detalhada_descricao as fonte,
                        1 as origem,
                        dt_ingest
                    from {{ ref("execucao_ne") }}

                    union all

                    select
                        fonte_recursos_detalhada,
                        fonte_recursos_detalhada_descricao,
                        2,
                        null
                    from {{ ref("emenda_dotacao") }}
                ) as fontes
            order by codigo_fonte, origem, dt_ingest desc
        ) as f

    union all

    select -1::bigint, '-1', 'Não identificado'
{% endmacro %}
```

- [ ] **Step 3: Formatar, reconstruir as dimensões dos dois marts e conferir**

Run (da raiz): sqlfmt nas 4 macros.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s dim_emenda dim_acao_orcamentaria dim_natureza_despesa dim_fonte_recurso teds_dim_emenda teds_dim_acao_orcamentaria teds_dim_natureza_despesa teds_dim_fonte_recurso`
Expected: `ERROR=0` e `WARN=0` (os `relationships` das fatos de Convênios e TEDs continuam passando).

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "
select 'emenda', count(*) from mir_convenios.dim_emenda union all
select 'acao', count(*) from mir_convenios.dim_acao_orcamentaria union all
select 'natureza', count(*) from mir_convenios.dim_natureza_despesa union all
select 'fonte', count(*) from mir_convenios.dim_fonte_recurso" -c "
select 'emenda', md5(string_agg(t::text, ',' order by sk_emenda)) from mir_convenios.dim_emenda t where codigo_emenda in (select codigo_emenda from mir_silver.emenda_ne) or sk_emenda = -1 union all
select 'acao', md5(string_agg(t::text, ',' order by sk_acao_orcamentaria)) from mir_convenios.dim_acao_orcamentaria t where ptres in (select ptres from mir_silver.execucao_ne) or sk_acao_orcamentaria = -1 union all
select 'natureza', md5(string_agg(t::text, ',' order by sk_natureza_despesa)) from mir_convenios.dim_natureza_despesa t where natureza_despesa in (select natureza_despesa from mir_silver.execucao_ne) or sk_natureza_despesa = -1 union all
select 'fonte', md5(string_agg(t::text, ',' order by sk_fonte_recurso)) from mir_convenios.dim_fonte_recurso t"
```
Expected: `emenda|93`, `acao|151`, `natureza|51`, `fonte|34`; e os md5 dos membros antigos iguais aos do Step 1.

- [ ] **Step 4: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir/macros/mir_gold
P="$M/dim_emenda.sql $M/dim_acao_orcamentaria.sql $M/dim_natureza_despesa.sql $M/dim_fonte_recurso.sql"
git add -- $P
git commit -m "feat(dbt/mir): dimensoes compartilhadas cobrem os codigos da dotacao das emendas" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 4: Gold — schema `mir_emendas` e dimensões

**Files:**
- Modify: `dbt_project.yml`
- Create: `models/mir_emendas/emendas_dim_tempo.sql`, `emendas_dim_unidade_gestora.sql`, `emendas_dim_acao_orcamentaria.sql`, `emendas_dim_natureza_despesa.sql`, `emendas_dim_fonte_recurso.sql`, `emendas_dim_emenda.sql`, `emendas_dim_parlamentar.sql` (alias + macro)
- Create: `models/mir_emendas/emendas_dim_instrumento_executor.sql`, `emendas_dim_favorecido.sql`, `emendas_dim_localidade.sql`
- Create: `models/mir_emendas/schema.yml`

**Interfaces:**
- Consumes: macros de `macros/mir_gold/`; `ref("emenda_instrumento")`, `ref("execucao_ne")`, `ref("emenda_ne")`, `ref("emenda_dotacao")`.
- Produces (chave natural → FK nas fatos):
  - `emendas_dim_instrumento_executor.sk_instrumento_executor` ← `fk(["nullif(x.sistema_instrumento, 'Não identificado')", "x.nr_instrumento"])`
  - `emendas_dim_favorecido.sk_favorecido` ← `fk(["x.favorecido_documento"])` (documento completo; o exibido é mascarado quando CPF)
  - `emendas_dim_localidade.sk_localidade` ← `fk(["<localizador_gasto>"])`
  - as 7 compartilhadas, com as chaves de sempre.

- [ ] **Step 1: Configurar o schema em `dbt_project.yml`**

Depois do bloco `mir_teds:`, acrescentar:

```yaml
    mir_emendas:
      +materialized: table
      +schema: mir_emendas
```

- [ ] **Step 2: Criar as 7 dimensões compartilhadas**

Cada arquivo tem duas linhas, alias e macro; por exemplo, `models/mir_emendas/emendas_dim_tempo.sql`:

```sql
{{ config(alias="dim_tempo") }}
{{ dim_tempo() }}
```

Do mesmo jeito: `emendas_dim_unidade_gestora.sql`, `emendas_dim_acao_orcamentaria.sql`, `emendas_dim_natureza_despesa.sql`, `emendas_dim_fonte_recurso.sql`, `emendas_dim_emenda.sql`, `emendas_dim_parlamentar.sql`.

- [ ] **Step 3: Criar `models/mir_emendas/emendas_dim_instrumento_executor.sql`**

```sql
{{ config(alias="dim_instrumento_executor") }}

-- Instrumentos que executam as emendas: convenio, fomento, colaboracao ou
-- parceria do MIR, TED, ou convenio de outro orgao. O membro -1 e a execucao
-- direta / nao identificada (NE de emenda sem instrumento encontrado).
select
    {{ surrogate_key(["sistema_instrumento", "nr_instrumento"]) }}
    as sk_instrumento_executor,
    sistema_instrumento,
    nr_instrumento,
    tipo_instrumento,
    objeto,
    situacao,
    executor_nome
from {{ ref("emenda_instrumento") }}

union all

select
    -1::bigint,
    'Não identificado',
    '-1',
    'Execução direta / não identificado',
    null,
    null,
    null
```

- [ ] **Step 4: Criar `models/mir_emendas/emendas_dim_favorecido.sql`**

```sql
{{ config(alias="dim_favorecido") }}

-- Favorecidos das NEs de emenda, pelo CPF/CNPJ. CPF de pessoa fisica aparece
-- mascarado (***12345***, mesmo formato do SICONV); a chave usa o documento
-- completo. Nome da NE mais recente.
select
    {{ surrogate_key(["favorecido_documento"]) }} as sk_favorecido,
    case
        when length(favorecido_documento) = 11
        then '***' || substr(favorecido_documento, 4, 5) || '***'
        else favorecido_documento
    end as favorecido_documento,
    favorecido_nome,
    case
        length(favorecido_documento)
        when 14
        then 'PJ'
        when 11
        then 'PF'
        else 'Não identificado'
    end as favorecido_tipo
from
    (
        select distinct on (favorecido_documento) favorecido_documento, favorecido_nome
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null and favorecido_documento is not null
        order by favorecido_documento, data_emissao desc
    ) as f

union all

select -1::bigint, '-1', 'Não identificado', 'Não identificado'
```

- [ ] **Step 5: Criar `models/mir_emendas/emendas_dim_localidade.sql`**

```sql
{{ config(alias="dim_localidade") }}

-- Localizador do gasto das emendas (NEs e dotacao): regiao e UF, ou NACIONAL.
-- Com NE, os atributos vem da NE.
select
    {{ surrogate_key(["localizador_gasto"]) }} as sk_localidade,
    localizador_gasto,
    localizador_descricao,
    regiao,
    uf,
    uf_nome
from
    (
        select distinct on (localizador_gasto)
            localizador_gasto, localizador_descricao, regiao, uf, uf_nome
        from
            (
                select
                    localizador_gasto,
                    localizador_descricao,
                    regiao,
                    uf,
                    uf_nome,
                    1 as origem
                from {{ ref("emenda_ne") }}

                union all

                select
                    localizador_gasto,
                    localizador_descricao,
                    regiao,
                    uf,
                    uf_nome,
                    2 as origem
                from {{ ref("emenda_dotacao") }}
            ) as fontes
        order by localizador_gasto, origem, localizador_descricao
    ) as l

union all

select -1::bigint, '-1', 'Não identificado', null, null, null
```

- [ ] **Step 6: Criar `models/mir_emendas/schema.yml`**

```yaml
version: 2

models:
  - name: emendas_dim_tempo
    description: "Calendario diario de 2000 a 2040 (macro compartilhada); sk_tempo = AAAAMMDD; -1 = sem data."
    columns:
      - name: sk_tempo
        tests: [unique, not_null, membro_nao_identificado]

  - name: emendas_dim_unidade_gestora
    description: "UG responsavel das NEs (macro compartilhada)."
    columns:
      - name: sk_unidade_gestora
        tests: [unique, not_null, membro_nao_identificado]

  - name: emendas_dim_acao_orcamentaria
    description: "Classificacao programatica no grao do PTRES (macro compartilhada; NEs e dotacao)."
    columns:
      - name: sk_acao_orcamentaria
        tests: [unique, not_null, membro_nao_identificado]

  - name: emendas_dim_natureza_despesa
    description: "Natureza de despesa, GND e modalidade de aplicacao (macro compartilhada; NEs e dotacao)."
    columns:
      - name: sk_natureza_despesa
        tests: [unique, not_null, membro_nao_identificado]

  - name: emendas_dim_fonte_recurso
    description: "Fonte de recursos detalhada (macro compartilhada; NEs e dotacao)."
    columns:
      - name: sk_fonte_recurso
        tests: [unique, not_null, membro_nao_identificado]

  - name: emendas_dim_emenda
    description: "Emenda parlamentar: codigo, ano, numero e autor (macro compartilhada; NEs e dotacao)."
    columns:
      - name: sk_emenda
        tests: [unique, not_null, membro_nao_identificado]
      - name: codigo_emenda
        tests: [unique, not_null]

  - name: emendas_dim_parlamentar
    description: >
      Parlamentar x cargo x partido (SCD2, macro compartilhada). As janelas
      podem se sobrepor entre partidos do mesmo parlamentar: para filtrar por
      data, use a fato, nao a dimensao.
    columns:
      - name: sk_parlamentar
        tests: [unique, not_null, membro_nao_identificado]

  - name: emendas_dim_instrumento_executor
    description: >
      Instrumentos que executam as emendas: Convênio, Fomento, Colaboração,
      Parceria, TED ou Convênio de outro órgão; -1 = Execução direta / não
      identificado.
    columns:
      - name: sk_instrumento_executor
        tests: [unique, not_null, membro_nao_identificado]
      - name: tipo_instrumento
        tests:
          - not_null
          - accepted_values:
              values: ["Convênio", "Fomento", "Colaboração", "Parceria", "TED", "Convênio de outro órgão", "Execução direta / não identificado"]

  - name: emendas_dim_favorecido
    description: "Favorecidos das NEs de emenda (CPF mascarado; chave pelo documento completo)."
    columns:
      - name: sk_favorecido
        tests: [unique, not_null, membro_nao_identificado]

  - name: emendas_dim_localidade
    description: "Localizador do gasto das emendas: regiao e UF, ou NACIONAL."
    columns:
      - name: sk_localidade
        tests: [unique, not_null, membro_nao_identificado]
      - name: localizador_gasto
        tests: [unique, not_null]
```

- [ ] **Step 7: Formatar, construir e conferir**

Run (da raiz): sqlfmt em `models/mir_emendas`.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s path:models/mir_emendas`
Expected: `ERROR=0` e `WARN=0`.

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "
select 'emenda', count(*) from mir_emendas.dim_emenda union all
select 'instrumento', count(*) from mir_emendas.dim_instrumento_executor union all
select 'favorecido', count(*) from mir_emendas.dim_favorecido union all
select 'localidade', count(*) from mir_emendas.dim_localidade union all
select 'acao', count(*) from mir_emendas.dim_acao_orcamentaria union all
select 'natureza', count(*) from mir_emendas.dim_natureza_despesa"
```
Expected: `emenda|93`, `instrumento|196`, `favorecido|143`, `acao|151`, `natureza|51`; `localidade` = número de localizadores distintos em `emenda_ne` ∪ `emenda_dotacao` + 1 (registrar no relatório).

- [ ] **Step 8: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/dbt_project.yml $M/models/mir_emendas/schema.yml"
for d in dim_tempo dim_unidade_gestora dim_acao_orcamentaria dim_natureza_despesa dim_fonte_recurso dim_emenda dim_parlamentar dim_instrumento_executor dim_favorecido dim_localidade; do
  P="$P $M/models/mir_emendas/emendas_$d.sql"
done
git add -- $P
git commit -m "feat(dbt/mir): dimensoes do mart mir_emendas" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 5: Gold — fatos de execução e de dotação

**Files:**
- Create: `models/mir_emendas/emendas_fato_execucao_orcamentaria.sql`, `models/mir_emendas/emendas_fato_dotacao.sql`
- Modify: `models/mir_emendas/schema.yml` (acrescentar em `models:`)
- Test: `tests/mir_emendas/mir_emendas_reconciliacao.sql`

**Interfaces:**
- Consumes: `fk`, `sk_tempo`; dimensões da Tarefa 4; `ref("execucao_ne")`, `ref("emenda_ne")`, `ref("emenda_dotacao")`.
- Produces: `mir_emendas.fato_execucao_orcamentaria` (PK `id_execucao_ne`) e `mir_emendas.fato_dotacao` (PK `id_movimento`).

- [ ] **Step 1: Escrever `tests/mir_emendas/mir_emendas_reconciliacao.sql`**

```sql
-- Falha se as fatos de Emendas perderem ou duplicarem linhas ou valores em
-- relacao a silver.
with
    comparacao as (
        select
            'fato_execucao_orcamentaria' as fato,
            (
                select count(*) from {{ ref("emendas_fato_execucao_orcamentaria") }}
            ) as linhas_fato,
            (
                select count(*)
                from {{ ref("execucao_ne") }}
                where codigo_emenda is not null
            ) as linhas_silver,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_inscritos), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from {{ ref("emendas_fato_execucao_orcamentaria") }}
            ) as valor_fato,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_inscritos), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from {{ ref("execucao_ne") }}
                where codigo_emenda is not null
            ) as valor_silver

        union all

        select
            'fato_dotacao',
            (select count(*) from {{ ref("emendas_fato_dotacao") }}),
            (select count(*) from {{ ref("emenda_dotacao") }}),
            (
                select coalesce(sum(dotacao_inicial), 0) + coalesce(sum(dotacao_atualizada), 0)
                from {{ ref("emendas_fato_dotacao") }}
            ),
            (
                select coalesce(sum(dotacao_inicial), 0) + coalesce(sum(dotacao_atualizada), 0)
                from {{ ref("emenda_dotacao") }}
            )
    )

select *
from comparacao
where linhas_fato <> linhas_silver or valor_fato <> valor_silver
```

- [ ] **Step 2: Criar `models/mir_emendas/emendas_fato_execucao_orcamentaria.sql`**

```sql
{{ config(alias="fato_execucao_orcamentaria") }}

-- Execucao orcamentaria das emendas: todas as linhas do nucleo com codigo de
-- emenda, de qualquer instrumento (convenio do MIR, TED, convenio de outro
-- orgao ou execucao direta / nao identificado). A emenda, o parlamentar e o
-- localizador vem da NE.
select
    x.id_execucao_ne,
    x.ne_ccor,
    {{ fk(["x.codigo_emenda"]) }} as sk_emenda,
    {{ fk(["e.id_parlamentar", "e.cargo_parlamentar", "e.sigla_partido"]) }}
    as sk_parlamentar,
    {{ fk(["nullif(x.sistema_instrumento, 'Não identificado')", "x.nr_instrumento"]) }}
    as sk_instrumento_executor,
    {{ fk(["x.favorecido_documento"]) }} as sk_favorecido,
    {{ fk(["e.localizador_gasto"]) }} as sk_localidade,
    {{ sk_tempo("x.data_emissao") }} as sk_tempo,
    {{ fk(["x.ug_responsavel_codigo"]) }} as sk_unidade_gestora,
    {{ fk(["x.ptres"]) }} as sk_acao_orcamentaria,
    {{ fk(["x.natureza_despesa"]) }} as sk_natureza_despesa,
    {{ fk(["x.fonte_recursos_detalhada"]) }} as sk_fonte_recurso,
    x.metodo_vinculo,
    x.inscricao_rap,
    x.reinscricao_rap,
    x.despesas_empenhadas,
    x.despesas_liquidadas,
    x.despesas_pagas,
    x.restos_a_pagar_inscritos,
    -- RAP inscrito sem as reinscricoes (saldo nao pago do mesmo dinheiro): e a
    -- medida que pode ser somada entre exercicios
    case
        when x.reinscricao_rap then 0 else x.restos_a_pagar_inscritos
    end as restos_a_pagar_inscritos_acumulavel,
    x.restos_a_pagar_pagos
from {{ ref("execucao_ne") }} as x
left join {{ ref("emenda_ne") }} as e on e.ne_ccor = x.ne_ccor
where x.codigo_emenda is not null
```

- [ ] **Step 3: Criar `models/mir_emendas/emendas_fato_dotacao.sql`**

```sql
{{ config(alias="fato_dotacao") }}

-- Dotacao das emendas, um movimento por linha (lancamentos positivos e
-- negativos; a soma e a dotacao do periodo). O parlamentar e o autor vigente na
-- data do movimento.
select
    d.id_movimento,
    {{ fk(["d.codigo_emenda"]) }} as sk_emenda,
    {{ fk(["d.id_parlamentar", "d.cargo_parlamentar", "d.sigla_partido"]) }}
    as sk_parlamentar,
    {{ sk_tempo("d.data_movimento") }} as sk_tempo,
    {{ fk(["d.ptres"]) }} as sk_acao_orcamentaria,
    {{ fk(["d.natureza_despesa"]) }} as sk_natureza_despesa,
    {{ fk(["d.fonte_recursos_detalhada"]) }} as sk_fonte_recurso,
    {{ fk(["d.localizador_gasto"]) }} as sk_localidade,
    d.modalidade_aplicacao,
    d.dotacao_inicial,
    d.dotacao_atualizada
from {{ ref("emenda_dotacao") }} as d
```

- [ ] **Step 4: Documentar em `models/mir_emendas/schema.yml` (acrescentar em `models:`)**

```yaml
  - name: emendas_fato_execucao_orcamentaria
    description: >
      Execucao orcamentaria (SIAFI) das emendas, no grao da linha do relatorio
      do Tesouro, de qualquer instrumento. Some restos_a_pagar_inscritos_acumulavel
      entre exercicios; restos_a_pagar_inscritos inclui as reinscricoes.
    columns:
      - name: id_execucao_ne
        tests: [unique, not_null]
      - name: sk_emenda
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_emenda'), field: sk_emenda}
      - name: sk_parlamentar
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_parlamentar'), field: sk_parlamentar}
      - name: sk_instrumento_executor
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_instrumento_executor'), field: sk_instrumento_executor}
      - name: sk_favorecido
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_favorecido'), field: sk_favorecido}
      - name: sk_localidade
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_localidade'), field: sk_localidade}
      - name: sk_tempo
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_tempo'), field: sk_tempo}
      - name: sk_unidade_gestora
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_unidade_gestora'), field: sk_unidade_gestora}
      - name: sk_acao_orcamentaria
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_acao_orcamentaria'), field: sk_acao_orcamentaria}
      - name: sk_natureza_despesa
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_natureza_despesa'), field: sk_natureza_despesa}
      - name: sk_fonte_recurso
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_fonte_recurso'), field: sk_fonte_recurso}

  - name: emendas_fato_dotacao
    description: "Dotacao das emendas, um movimento por linha (lancamentos positivos e negativos)."
    columns:
      - name: id_movimento
        tests: [unique, not_null]
      - name: sk_emenda
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_emenda'), field: sk_emenda}
      - name: sk_parlamentar
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_parlamentar'), field: sk_parlamentar}
      - name: sk_tempo
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_tempo'), field: sk_tempo}
      - name: sk_acao_orcamentaria
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_acao_orcamentaria'), field: sk_acao_orcamentaria}
      - name: sk_natureza_despesa
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_natureza_despesa'), field: sk_natureza_despesa}
      - name: sk_fonte_recurso
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_fonte_recurso'), field: sk_fonte_recurso}
      - name: sk_localidade
        tests:
          - not_null
          - relationships: {to: ref('emendas_dim_localidade'), field: sk_localidade}
```

- [ ] **Step 5: Formatar, construir e conferir**

Run (da raiz): sqlfmt nos 2 modelos e no teste.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s emendas_fato_execucao_orcamentaria emendas_fato_dotacao`
Expected: `ERROR=0` e `WARN=0` (inclui `mir_emendas_reconciliacao`).

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At \
 -c "select count(*), count(distinct ne_ccor), sum(despesas_empenhadas), sum(despesas_liquidadas), sum(despesas_pagas), sum(restos_a_pagar_inscritos_acumulavel), sum(restos_a_pagar_pagos) from mir_emendas.fato_execucao_orcamentaria" \
 -c "select i.tipo_instrumento, count(distinct f.ne_ccor), sum(f.despesas_empenhadas) from mir_emendas.fato_execucao_orcamentaria f join mir_emendas.dim_instrumento_executor i using (sk_instrumento_executor) group by 1 order by 1" \
 -c "select count(*), sum(dotacao_inicial), sum(dotacao_atualizada), count(*) filter (where sk_parlamentar = -1) from mir_emendas.fato_dotacao"
```
Expected: `651|221|55822240.37|23534892.51|22537602.51|23136594.77|19760949.24`; por tipo, SICONV do MIR somando 207 NEs e 51.672.240,37 entre Convênio e Fomento, `Convênio de outro órgão|3|900000.00`, `TED|4|1650000.00`, `Execução direta / não identificado|7|1600000.00`; dotação `1058|65121784.00|63829841.00|46`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/models/mir_emendas/emendas_fato_execucao_orcamentaria.sql $M/models/mir_emendas/emendas_fato_dotacao.sql $M/models/mir_emendas/schema.yml $M/tests/mir_emendas/mir_emendas_reconciliacao.sql"
git add -- $P
git commit -m "feat(dbt/mir): fatos de execucao e dotacao das emendas" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 6: Gold — posição por emenda e consistência entre os marts

**Files:**
- Create: `models/mir_emendas/emendas_fato_emenda_posicao.sql`
- Modify: `models/mir_emendas/schema.yml` (acrescentar em `models:`)
- Test: `tests/mir_emendas/emendas_fato_emenda_posicao_consistente.sql`
- Test: `tests/mir_emendas/consistencia_entre_marts.sql`

**Interfaces:**
- Consumes: `fk`; `emendas_dim_emenda`; as fatos da Tarefa 5; `ref("execucao_ne")`, `ref("emenda_dotacao")`; e, no teste entre marts, `ref("fato_execucao_orcamentaria")` (Convênios), `ref("teds_fato_execucao_orcamentaria")`, `ref("emendas_fato_execucao_orcamentaria")`, `ref("emendas_dim_instrumento_executor")`.
- Produces: `mir_emendas.fato_emenda_posicao`, uma linha por emenda com dotação ou NE (PK `sk_emenda`).

Teste entre marts (spec §11): o empenhado de emenda nos marts de Convênios e TEDs, mais o empenhado de emenda em convênio de outro órgão e em execução direta / não identificada no mart de Emendas, é igual ao empenhado total do mart de Emendas.

- [ ] **Step 1: Escrever os testes**

`tests/mir_emendas/emendas_fato_emenda_posicao_consistente.sql`:

```sql
-- Falha se a posicao de alguma emenda divergir da soma das fatos, ou se
-- faltar/sobrar emenda.
with
    dotacao as (
        select
            sk_emenda,
            sum(dotacao_inicial) as inicial,
            sum(dotacao_atualizada) as atualizada
        from {{ ref("emendas_fato_dotacao") }}
        group by sk_emenda
    ),

    execucao as (
        select
            sk_emenda,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos_acumulavel) as rap_inscrito
        from {{ ref("emendas_fato_execucao_orcamentaria") }}
        group by sk_emenda
    ),

    emendas as (
        select sk_emenda
        from dotacao
        union
        select sk_emenda
        from execucao
    )

select coalesce(p.sk_emenda, e.sk_emenda) as sk_emenda
from {{ ref("emendas_fato_emenda_posicao") }} as p
full join emendas as e on e.sk_emenda = p.sk_emenda
left join dotacao as d on d.sk_emenda = p.sk_emenda
left join execucao as x on x.sk_emenda = p.sk_emenda
where
    p.sk_emenda is null
    or e.sk_emenda is null
    or p.dotacao_inicial <> coalesce(d.inicial, 0)
    or p.dotacao_atualizada <> coalesce(d.atualizada, 0)
    or p.despesas_empenhadas <> coalesce(x.empenhado, 0)
    or p.despesas_pagas <> coalesce(x.pago, 0)
    or p.restos_a_pagar_inscritos_acumulavel <> coalesce(x.rap_inscrito, 0)
```

`tests/mir_emendas/consistencia_entre_marts.sql`:

```sql
-- Falha se o empenhado de emenda nao fechar entre os tres marts (spec §11):
-- Convenios (origem Emenda) + TEDs (origem Emenda) + Emendas executadas por
-- convenio de outro orgao ou sem instrumento = total do mart de Emendas.
with
    convenios as (
        select coalesce(sum(despesas_empenhadas), 0) as v
        from {{ ref("fato_execucao_orcamentaria") }}
        where origem_recurso = 'Emenda'
    ),

    teds as (
        select coalesce(sum(despesas_empenhadas), 0) as v
        from {{ ref("teds_fato_execucao_orcamentaria") }}
        where origem_recurso = 'Emenda'
    ),

    fora_dos_marts as (
        select coalesce(sum(f.despesas_empenhadas), 0) as v
        from {{ ref("emendas_fato_execucao_orcamentaria") }} as f
        inner join
            {{ ref("emendas_dim_instrumento_executor") }} as i
            on i.sk_instrumento_executor = f.sk_instrumento_executor
        where
            i.tipo_instrumento
            in ('Convênio de outro órgão', 'Execução direta / não identificado')
    ),

    emendas as (
        select coalesce(sum(despesas_empenhadas), 0) as v
        from {{ ref("emendas_fato_execucao_orcamentaria") }}
    )

select
    c.v as convenios,
    t.v as teds,
    o.v as fora_dos_marts,
    e.v as total_emendas
from convenios as c, teds as t, fora_dos_marts as o, emendas as e
where c.v + t.v + o.v <> e.v
```

- [ ] **Step 2: Criar `models/mir_emendas/emendas_fato_emenda_posicao.sql`**

```sql
{{ config(alias="fato_emenda_posicao") }}

-- Posicao acumulada de cada emenda (snapshot), uma linha por emenda com
-- dotacao ou NE: dotacao (soma dos movimentos), execucao das NEs de emenda e
-- quantidade de NEs e de instrumentos. Execucao 0 quando a emenda so tem
-- dotacao (dinheiro reservado e ainda nao empenhado).
with
    dotacao as (
        select
            codigo_emenda,
            sum(dotacao_inicial) as dotacao_inicial,
            sum(dotacao_atualizada) as dotacao_atualizada
        from {{ ref("emenda_dotacao") }}
        group by codigo_emenda
    ),

    -- RAP inscrito sem as reinscricoes: o saldo nao pago reaparece como
    -- inscrito no exercicio seguinte e nao pode ser somado de novo
    execucao as (
        select
            codigo_emenda,
            sum(despesas_empenhadas) as despesas_empenhadas,
            sum(despesas_liquidadas) as despesas_liquidadas,
            sum(despesas_pagas) as despesas_pagas,
            sum(
                case when reinscricao_rap then 0 else restos_a_pagar_inscritos end
            ) as restos_a_pagar_inscritos_acumulavel,
            sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,
            count(distinct ne_ccor) as qtd_nes,
            count(
                distinct case
                    when sistema_instrumento <> 'Não identificado'
                    then sistema_instrumento || '|' || nr_instrumento
                end
            ) as qtd_instrumentos
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
        group by codigo_emenda
    ),

    emendas as (
        select codigo_emenda
        from dotacao
        union
        select codigo_emenda
        from execucao
    )

select
    {{ fk(["e.codigo_emenda"]) }} as sk_emenda,
    coalesce(d.dotacao_inicial, 0) as dotacao_inicial,
    coalesce(d.dotacao_atualizada, 0) as dotacao_atualizada,
    coalesce(x.despesas_empenhadas, 0) as despesas_empenhadas,
    coalesce(x.despesas_liquidadas, 0) as despesas_liquidadas,
    coalesce(x.despesas_pagas, 0) as despesas_pagas,
    coalesce(x.restos_a_pagar_inscritos_acumulavel, 0)
    as restos_a_pagar_inscritos_acumulavel,
    coalesce(x.restos_a_pagar_pagos, 0) as restos_a_pagar_pagos,
    coalesce(x.qtd_nes, 0) as qtd_nes,
    coalesce(x.qtd_instrumentos, 0) as qtd_instrumentos
from emendas as e
left join dotacao as d on d.codigo_emenda = e.codigo_emenda
left join execucao as x on x.codigo_emenda = e.codigo_emenda
```

- [ ] **Step 3: Documentar em `models/mir_emendas/schema.yml` (acrescentar em `models:`)**

```yaml
  - name: emendas_fato_emenda_posicao
    description: >
      Posicao acumulada por emenda (snapshot): dotacao, execucao das NEs de
      emenda e quantidades. Execucao 0 quando a emenda so tem dotacao.
    columns:
      - name: sk_emenda
        tests:
          - unique
          - not_null
          - relationships: {to: ref('emendas_dim_emenda'), field: sk_emenda}
```

- [ ] **Step 4: Formatar, construir e conferir**

Run (da raiz): sqlfmt no modelo e nos 2 testes.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s emendas_fato_emenda_posicao consistencia_entre_marts`
Expected: `ERROR=0` e `WARN=0`.

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "select count(*), sum(dotacao_inicial), sum(dotacao_atualizada), sum(despesas_empenhadas), count(*) filter (where qtd_nes = 0), sum(qtd_instrumentos) from mir_emendas.fato_emenda_posicao"
```
Expected: `92|65121784.00|63829841.00|55822240.37|6|` seguido da soma de instrumentos por emenda (registrar).

- [ ] **Step 5: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/models/mir_emendas/emendas_fato_emenda_posicao.sql $M/models/mir_emendas/schema.yml $M/tests/mir_emendas/emendas_fato_emenda_posicao_consistente.sql $M/tests/mir_emendas/consistencia_entre_marts.sql"
git add -- $P
git commit -m "feat(dbt/mir): posicao por emenda e consistencia entre os marts" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 7: Paridade com o gold antigo e verificação final

**Files:**
- Create: `analyses/paridade_mir_emendas.sql` (temporário: apagar na etapa 5)

**Interfaces:**
- Consumes: `emendas_fato_emenda_posicao`, `emendas_dim_emenda`, `emendas_fato_execucao_orcamentaria`, `emendas_dim_instrumento_executor`; `ref("resumo_emendas_orcamento_execucao")` e `ref("emendas_instrumentos_execucao")` (gold antigo, só leitura).
- Produces: uma linha por diferença (`bloco`, `chave`, `medida`, `valor_antigo`, `valor_novo`), em dois blocos: por autor (contra o resumo) e por NE (tipo do instrumento).

- [ ] **Step 1: Criar `analyses/paridade_mir_emendas.sql`**

```sql
-- Paridade temporaria (spec §11): mart de Emendas x gold antigo. Apagar na
-- etapa 5, junto com o gold antigo. Dois blocos:
-- * por autor, contra resumo_emendas_orcamento_execucao (dotacao e execucao);
-- * por NE, o tipo do instrumento, contra emendas_instrumentos_execucao.
with
    antigo_autor as (
        select
            autor_emendas_orcamento_nome as autor,
            dotacao_inicial,
            dotacao_atualizada,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            restos_a_pagar_inscritos,
            restos_a_pagar_pagos
        from {{ ref("resumo_emendas_orcamento_execucao") }}
    ),

    novo_autor as (
        select
            e.autor_nome as autor,
            sum(p.dotacao_inicial) as dotacao_inicial,
            sum(p.dotacao_atualizada) as dotacao_atualizada,
            sum(p.despesas_empenhadas) as despesas_empenhadas,
            sum(p.despesas_liquidadas) as despesas_liquidadas,
            sum(p.despesas_pagas) as despesas_pagas,
            sum(p.restos_a_pagar_inscritos_acumulavel) as restos_a_pagar_inscritos,
            sum(p.restos_a_pagar_pagos) as restos_a_pagar_pagos
        from {{ ref("emendas_fato_emenda_posicao") }} as p
        inner join {{ ref("emendas_dim_emenda") }} as e on e.sk_emenda = p.sk_emenda
        group by e.autor_nome
    ),

    por_autor as (
        select coalesce(a.autor, n.autor) as chave, c.medida, c.valor_antigo, c.valor_novo
        from antigo_autor as a
        full join novo_autor as n on n.autor = a.autor
        cross join
            lateral(
                values
                    (
                        'presenca',
                        (a.autor is not null)::text,
                        (n.autor is not null)::text,
                        a.autor is null or n.autor is null
                    ),
                    (
                        'dotacao_inicial',
                        a.dotacao_inicial::text,
                        n.dotacao_inicial::text,
                        coalesce(a.dotacao_inicial, 0) <> coalesce(n.dotacao_inicial, 0)
                    ),
                    (
                        'dotacao_atualizada',
                        a.dotacao_atualizada::text,
                        n.dotacao_atualizada::text,
                        coalesce(a.dotacao_atualizada, 0)
                        <> coalesce(n.dotacao_atualizada, 0)
                    ),
                    (
                        'empenhado',
                        a.despesas_empenhadas::text,
                        n.despesas_empenhadas::text,
                        coalesce(a.despesas_empenhadas, 0)
                        <> coalesce(n.despesas_empenhadas, 0)
                    ),
                    (
                        'liquidado',
                        a.despesas_liquidadas::text,
                        n.despesas_liquidadas::text,
                        coalesce(a.despesas_liquidadas, 0)
                        <> coalesce(n.despesas_liquidadas, 0)
                    ),
                    (
                        'pago',
                        a.despesas_pagas::text,
                        n.despesas_pagas::text,
                        coalesce(a.despesas_pagas, 0) <> coalesce(n.despesas_pagas, 0)
                    ),
                    (
                        'rap_inscrito',
                        a.restos_a_pagar_inscritos::text,
                        n.restos_a_pagar_inscritos::text,
                        coalesce(a.restos_a_pagar_inscritos, 0)
                        <> coalesce(n.restos_a_pagar_inscritos, 0)
                    ),
                    (
                        'rap_pago',
                        a.restos_a_pagar_pagos::text,
                        n.restos_a_pagar_pagos::text,
                        coalesce(a.restos_a_pagar_pagos, 0)
                        <> coalesce(n.restos_a_pagar_pagos, 0)
                    )
            ) as c(medida, valor_antigo, valor_novo, difere)
        -- As medidas so sao comparadas nos autores presentes nos dois lados
        where
            c.difere
            and (c.medida = 'presenca' or (a.autor is not null and n.autor is not null))
    ),

    antigo_ne as (
        select ne_ccor, max(tipo_instrumento) as tipo
        from {{ ref("emendas_instrumentos_execucao") }}
        group by ne_ccor
    ),

    novo_ne as (
        select f.ne_ccor, max(i.tipo_instrumento) as tipo
        from {{ ref("emendas_fato_execucao_orcamentaria") }} as f
        inner join
            {{ ref("emendas_dim_instrumento_executor") }} as i
            on i.sk_instrumento_executor = f.sk_instrumento_executor
        group by f.ne_ccor
    ),

    por_ne as (
        select n.ne_ccor as chave, 'tipo_instrumento' as medida, a.tipo, n.tipo
        from novo_ne as n
        left join antigo_ne as a on a.ne_ccor = n.ne_ccor
        where
            case
                a.tipo
                when 'TERMO DE FOMENTO'
                then 'Fomento'
                when 'CONVENIO'
                then 'Convênio'
                when 'TED'
                then 'TED'
                else 'Execução direta / não identificado'
            end
            is distinct from n.tipo
    )

select 'autor' as bloco, chave, medida, valor_antigo, valor_novo
from por_autor

union all

select 'ne' as bloco, *
from por_ne
```

- [ ] **Step 2: Compilar, rodar e classificar**

Run:
```bash
poetry run dbt compile --profiles-dir . --no-partial-parse -s paridade_mir_emendas
Q=$(cat target/compiled/mir/analyses/paridade_mir_emendas.sql)
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "select bloco, medida, valor_antigo, valor_novo, count(*) from ($Q) as x group by 1, 2, 3, 4 order by 1, 2, 5 desc"
```

Diferenças já esperadas:
- `rap_inscrito`: regra do usuário (o novo soma o RAP sem as reinscrições, spec §13).
- `tipo_instrumento`: o gold antigo acha o instrumento por outro regex e não separa o convênio de outro órgão (`CONVENIO` antigo pode virar `Convênio de outro órgão`) nem as NEs que o núcleo não liga.

Qualquer outra medida (dotação, empenhado, liquidado, pago, RAP pago ou presença de autor) é regressão: listar os casos e parar para relatar. Registrar a tabela final de diferenças no fim deste plano, com a classificação de cada uma.

- [ ] **Step 3: Construir tudo o que a remodelagem criou**

Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s path:models/mir_silver path:models/mir_convenios path:models/mir_teds path:models/mir_emendas uf_regiao ugs_mir empenhos_por_plano_acao`
Expected: `ERROR=0`; `WARN=1` (o aviso de complemento próprio da silver de convênios, linha de base 2).

- [ ] **Step 4: Confirmar que nenhum outro modelo antigo mudou**

Run (da raiz): `git diff 5d35b3e --stat -- airflow_lappis/dags/dbt/mir/models ':!airflow_lappis/dags/dbt/mir/models/mir_silver' ':!airflow_lappis/dags/dbt/mir/models/mir_convenios' ':!airflow_lappis/dags/dbt/mir/models/mir_teds' ':!airflow_lappis/dags/dbt/mir/models/mir_emendas'`
Expected: só `models/empenhos_ted_dbt/silver/empenhos_por_plano_acao.sql` (casca da etapa 3).

- [ ] **Step 5: Lint**

Run (da raiz): sqlfmt `--check` em `models/mir_silver`, `models/mir_emendas`, `tests/mir_silver`, `tests/mir_emendas`, `macros/mir_gold`, `macros/mir_silver` e `analyses` (caminhos sob `airflow_lappis/dags/dbt/mir/`).
Expected: todos passam.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P="airflow_lappis/dags/dbt/mir/analyses/paridade_mir_emendas.sql docs/superpowers/plans/2026-09-29-etapa-4-emendas.md"
git add -- $P
git commit -m "test(dbt/mir): paridade temporaria de mir_emendas com o gold antigo" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

## Fora desta etapa

- Etapa 5: migração do I1 para os marts novos (o I1 pode mudar onde o modelo novo cobre mais cenários; cada mudança listada no PR), remoção do gold e da silver antigos, das análises de paridade, da casca `empenhos_por_plano_acao` e do teste antigo quebrado `test_ted_resumo_orcamentario_grao_unico`; `drop table` explícito das tabelas órfãs; lista dos painéis do Power BI afetados.
