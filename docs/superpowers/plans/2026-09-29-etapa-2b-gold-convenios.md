# Etapa 2b: Gold de Convênios (`mir_convenios`) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o data mart `mir_convenios` (dimensões, fatos transacionais e posição por convênio) para o Power BI de Convênios/Termos de Fomento, com as macros das dimensões compartilhadas e a paridade contra `resumo_convenios` / `resumo_termos_fomento`.

**Architecture:** A silver (`mir_silver`) concentra as regras; o gold só monta a estrela. Chaves substitutas são `bigint` derivados por md5 da chave natural, calculados com a mesma macro na dimensão e na fato (sem join); `relationships` garante que cada FK existe. Dimensões repetidas entre marts são macros em `macros/mir_gold/`; cada mart materializa a sua cópia com uma linha (`{{ dim_tempo() }}`). Toda dimensão tem o membro `-1` (Não identificado).

**Tech Stack:** dbt-core/dbt-postgres 1.7.13, PostgreSQL 17 (container `mir-dump-pg17`, porta 5433, database `analytics`), shandy-sqlfmt 0.32.0.

**Spec:** `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§4, §5, §6, §11).

## Global Constraints

- Gold em `models/mir_convenios/`, schema `mir_convenios`, materialização `table` (configurado na Tarefa 3). Silver em `models/mir_silver/`.
- Nenhum modelo fora de `mir_silver` e `mir_convenios` é alterado. Bronze e gold antigo intocados (o gold antigo só é lido pela análise de paridade).
- Chave substituta: `('x' || substr(md5(<chave natural>), 1, 16))::bit(64)::bigint` via macro `surrogate_key`; `sk_tempo` = `AAAAMMDD`; FK nula vira `-1`.
- Toda dimensão tem a linha `sk = -1` com rótulo `Não identificado` (ou `Não identificada` para origem do recurso).
- Nada no silver depende da data de hoje. No gold, só a `dim_convenio` usa `current_date`, exposto como `data_referencia`.
- RAP: a medida somável entre exercícios exclui `reinscricao_rap = true` (spec §13).
- Convênios de outros órgãos com NE no relatório do MIR (24 convênios, 145 linhas) ficam fora deste mart: a fato de execução só leva NEs cujo `nr_instrumento` está em `convenio_mir`.
- Literais de dados levam acento (`Não identificado`, `Recurso próprio`); comentários SQL em português sem acentos.
- Todo `.sql` novo ou alterado passa pelo sqlfmt antes do commit.
- Commits só com os arquivos da tarefa (`git add -- <paths>` e `git commit ... -- <paths>`); há ~90 arquivos de `dicionario-mir/` em stage que não fazem parte deste trabalho e não podem ser commitados, retirados do stage nem resetados. Único trailer permitido: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Nunca rodar `dbt build/run` sem `-s`, nunca usar operadores `+`, nunca `--full-refresh`.

### Ambiente local (usado em todos os comandos)

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
export DB_DW_HOST_MIR=localhost DB_DW_PORT_MIR=5433 DB_DW_USER_MIR=postgres \
       DB_DW_PASSWORD_MIR=postgres DB_DW_DBNAME_MIR=analytics DB_DW_SCHEMA_MIR=mir
```

- Todo comando dbt: `poetry run dbt <cmd> --profiles-dir . --no-partial-parse ...` (o cache de parse parcial esconde testes novos).
- sqlfmt (não está no poetry), a partir da raiz do repositório: `/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad/sqlfmt-venv/bin/sqlfmt <arquivos>`.
- Consultas: `docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "<sql>"`.

### Linha de base medida em 2026-09-29 (dump local)

| Objeto | Linhas esperadas |
|---|---|
| `mir_silver.emenda_ne` | 221 NEs, 86 emendas; `prioridade_match` 1 = 210, 3 = 11 (4 autores sem cadastro: Augusto Puppio, Guilherme Boulos, Paulão, Reginete Bispo) |
| `dim_tempo` | 14.977 (2000-01-01 a 2040-12-31 + `-1`) |
| `dim_unidade_gestora` / `dim_acao_orcamentaria` / `dim_natureza_despesa` / `dim_fonte_recurso` | 71 / 143 / 40 / 34 |
| `dim_emenda` / `dim_parlamentar` | 87 / 1.242 |
| `dim_convenio` / `dim_convenente` / `dim_localidade` / `dim_fornecedor` | 644 / 422 / 179 / 5.420 |
| `fato_execucao_orcamentaria` | 751 linhas, 254 NEs; empenhado 77.251.024,63; liquidado 44.951.599,26; pago 43.954.309,26; RAP inscrito sem reinscrição 22.848.672,28; RAP pago 18.519.367,24 |
| `fato_fluxo_financeiro` | 22.438 |
| `fato_cronograma_desembolso` | 1.177 (176.471.172,94) |
| `fato_evento_convenio` | 15.903 |
| `fato_convenio_posicao` | 643; empenhado SICONV 143.870.442,64 (905 empenhos) |

Fornecedores (pagamentos dos convênios do MIR): PJ 11.717 pagamentos / 3.003 fornecedores; PF 6.608 / 2.416 (CPF mascarado na origem, `***12345***`); sem documento válido 2.586 pagamentos (R$ 7.914.906,56) → `-1`.

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `models/mir_silver/convenio_movimento_financeiro.sql` | Modify | tipo e chave do fornecedor |
| `models/mir_silver/convenio_contagens.sql` | Modify | empenhos registrados no SICONV |
| `models/mir_silver/emenda_ne.sql` | Create | NE de emenda → emenda e parlamentar na data de emissão |
| `models/mir_silver/schema.yml` | Modify | documentação e testes das mudanças |
| `tests/mir_silver/convenio_contagens_ids_unicos.sql` | Modify | trava também para empenhos |
| `tests/mir_silver/emenda_ne_cobertura.sql`, `emenda_ne_autor_sem_cadastro.sql` | Create | testes de `emenda_ne` |
| `dbt_project.yml` | Modify | schema `mir_convenios` |
| `macros/mir_gold/chaves.sql` | Create | `surrogate_key`, `fk`, `sk_tempo` |
| `macros/mir_gold/dim_*.sql` | Create | uma macro por dimensão compartilhada |
| `tests/generic/membro_nao_identificado.sql` | Create | teste genérico: dimensão tem `-1` |
| `seeds/uf_regiao.csv`, `seeds/schema.yml` | Create / Modify | UF → nome e região |
| `models/mir_convenios/dim_*.sql`, `fato_*.sql`, `schema.yml` | Create | o mart |
| `tests/mir_convenios/*.sql` | Create | reconciliação e consistência |
| `analyses/paridade_mir_convenios.sql` | Create | paridade temporária com o gold antigo (apagar na etapa 5) |

Todos os caminhos são relativos a `airflow_lappis/dags/dbt/mir/`, exceto os de `docs/`.

---

### Task 1: Silver — fornecedor e empenhos do SICONV

**Files:**
- Modify: `models/mir_silver/convenio_movimento_financeiro.sql` (arquivo inteiro abaixo)
- Modify: `models/mir_silver/convenio_contagens.sql`
- Modify: `models/mir_silver/schema.yml`
- Modify: `tests/mir_silver/convenio_contagens_ids_unicos.sql`

**Interfaces:**
- Consumes: `ref("pagamento")` (`identif_fornecedor`, `nome_fornecedor`), `ref("empenho")` (bronze SICONV: `id_empenho`, `nr_convenio`, `valor_empenho`).
- Produces: `convenio_movimento_financeiro` ganha `fornecedor_tipo text` (`PF` · `PJ` · nulo) e `fornecedor_chave text` (PJ: CNPJ; PF: documento mascarado + `|` + nome; nulo sem documento válido). `fornecedor_documento` passa a ser o CNPJ (14 dígitos) ou o CPF mascarado (`***12345***`). `convenio_contagens` ganha `qtd_empenhos_siconv bigint` e `valor_empenhado_siconv numeric` (0 quando não há).

Por quê: o SICONV publica o CPF mascarado (`***23514***`); a versão atual guarda só os dígitos (`23514`), que colidem entre pessoas diferentes. E o empenhado do gold antigo vem da tabela `empenho` do SICONV (histórico completo, 635 convênios), que a posição precisa manter ao lado do empenhado SIAFI (225 convênios).

- [ ] **Step 1: Atualizar a trava de ids repetidos (teste primeiro)**

Substituir o conteúdo de `tests/mir_silver/convenio_contagens_ids_unicos.sql` por:

```sql
-- Falha se uma meta, licitacao ou empenho de convenio do MIR aparecer
-- repetido na origem: as contagens e somas de convenio_contagens usam count(*)
-- e sum() e seriam infladas pela repeticao.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    repetidos as (
        select 'meta' as tipo, id_meta::text as id, count(*) as qtd
        from {{ ref("meta_crono_fisico") }}
        where nr_convenio in (select nr_convenio from mir)
        group by id_meta
        having count(*) > 1

        union all

        select 'licitacao' as tipo, id_licitacao::text as id, count(*) as qtd
        from {{ ref("licitacao") }}
        where nr_convenio in (select nr_convenio from mir)
        group by id_licitacao
        having count(*) > 1

        union all

        select 'empenho' as tipo, id_empenho::text as id, count(*) as qtd
        from {{ ref("empenho") }}
        where nr_convenio in (select nr_convenio from mir)
        group by id_empenho
        having count(*) > 1
    )

select *
from repetidos
```

- [ ] **Step 2: Reescrever `convenio_movimento_financeiro.sql`**

Mudanças em relação à versão atual (commit 9cb6fcc): novo CTE `pagamentos` antes de `movimentos`; colunas `fornecedor_tipo` e `fornecedor_chave` em todos os ramos (nulas fora do pagamento); o ramo de pagamento lê de `pagamentos`. Conteúdo completo:

```sql
{{ config(materialized="table") }}

-- Movimentos financeiros dos convenios do MIR, uma linha por movimento. Une as
-- tabelas do SICONV que tem a mesma forma (convenio, data, valor) para que o BI
-- compare entradas e saidas numa fato so. A chave de cada tipo e a chave
-- natural da origem; contrapartida e tributo nao tem chave na origem e usam
-- data e valor (unicos nos dados atuais, garantidos pelo teste unique);
-- desbloqueio usa a linha inteira, sem as repeticoes da origem. O recorte do
-- MIR e aplicado em cada ramo, antes da uniao, para nao ler o SICONV inteiro.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    -- O SICONV publica o CPF mascarado (***12345***): o documento de pessoa
    -- fisica fica como veio, e a chave do fornecedor PF leva o nome, porque os
    -- 5 digitos visiveis nao identificam a pessoa sozinhos. CPF sem mascara e
    -- mascarado no mesmo formato. Documento sem formato de CPF ou CNPJ fica
    -- sem tipo e sem chave (fornecedor Nao identificado no gold).
    pagamentos as (
        select
            p.*,
            case
                when p.fornecedor_documento ~ '^\d{14}$'
                then 'PJ'
                when p.fornecedor_documento ~ '^\*{3}\d{5}\*{3}$'
                then 'PF'
            end as fornecedor_tipo
        from
            (
                select
                    nr_convenio,
                    nr_mov_fin,
                    data_pag,
                    vl_pago,
                    nr_dl,
                    case
                        when identif_fornecedor ~ '\*'
                        then upper(trim(identif_fornecedor))
                        when regexp_replace(identif_fornecedor, '\D', '', 'g') ~ '^\d{11}$'
                        then
                            '***'
                            || substr(regexp_replace(identif_fornecedor, '\D', '', 'g'), 4, 5)
                            || '***'
                        else nullif(regexp_replace(identif_fornecedor, '\D', '', 'g'), '')
                    end as fornecedor_documento,
                    nullif(trim(nome_fornecedor), '') as fornecedor_nome
                from {{ ref("pagamento") }}
                where nr_convenio in (select nr_convenio from mir)
            ) as p
    ),

    movimentos as (
        select
            nr_convenio,
            'Desembolso federal' as tipo_movimento,
            id_desembolso::text as chave_origem,
            data_desembolso as data_movimento,
            vl_desembolsado as valor,
            null::numeric as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            nr_siafi as documento_referencia
        from {{ ref("desembolso") }}
        where nr_convenio in (select nr_convenio from mir)

        union all

        select
            nr_convenio,
            'Contrapartida depositada' as tipo_movimento,
            concat_ws(
                '|', dt_ingresso_contrapartida, vl_ingresso_contrapartida
            ) as chave_origem,
            dt_ingresso_contrapartida as data_movimento,
            vl_ingresso_contrapartida as valor,
            null::numeric as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            null::text as documento_referencia
        from {{ ref("ingresso_contrapartida") }}
        where nr_convenio in (select nr_convenio from mir)

        union all

        select
            nr_convenio,
            'Desbloqueio' as tipo_movimento,
            concat_ws(
                '|',
                nr_ob,
                data_cadastro,
                data_envio,
                tipo_recurso_desbloqueio,
                vl_total_desbloqueio,
                vl_desbloqueado,
                vl_bloqueado
            ) as chave_origem,
            data_cadastro as data_movimento,
            vl_desbloqueado as valor,
            vl_bloqueado as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            nr_ob as documento_referencia
        -- O desbloqueio nao tem chave na origem e traz linhas identicas
        -- repetidas: remove as repeticoes e usa a linha inteira como chave
        from
            (
                select distinct *
                from {{ ref("desbloqueio") }}
                where nr_convenio in (select nr_convenio from mir)
            ) as d

        union all

        select
            nr_convenio,
            'Pagamento a fornecedor' as tipo_movimento,
            nr_mov_fin::text as chave_origem,
            data_pag as data_movimento,
            vl_pago as valor,
            null::numeric as valor_bloqueado,
            fornecedor_documento,
            fornecedor_nome,
            fornecedor_tipo,
            case
                when fornecedor_tipo = 'PJ'
                then fornecedor_documento
                when fornecedor_tipo = 'PF'
                then fornecedor_documento || '|' || coalesce(fornecedor_nome, '')
            end as fornecedor_chave,
            nr_dl as documento_referencia
        from pagamentos

        union all

        select
            nr_convenio,
            'Pagamento de tributo' as tipo_movimento,
            concat_ws('|', data_tributo, vl_pag_tributos) as chave_origem,
            data_tributo as data_movimento,
            vl_pag_tributos as valor,
            null::numeric as valor_bloqueado,
            null::text as fornecedor_documento,
            null::text as fornecedor_nome,
            null::text as fornecedor_tipo,
            null::text as fornecedor_chave,
            null::text as documento_referencia
        from {{ ref("pagamento_tributo") }}
        where nr_convenio in (select nr_convenio from mir)
    )

select
    md5(concat_ws('|', m.tipo_movimento, m.nr_convenio, m.chave_origem)) as id_movimento,
    m.nr_convenio,
    m.tipo_movimento,
    m.data_movimento,
    m.valor,
    m.valor_bloqueado,
    m.fornecedor_documento,
    m.fornecedor_nome,
    m.fornecedor_tipo,
    m.fornecedor_chave,
    m.documento_referencia
from movimentos as m
```

- [ ] **Step 3: Acrescentar os empenhos do SICONV em `convenio_contagens.sql`**

Acrescentar um CTE depois de `desembolsos` (com a vírgula antes):

```sql
    -- Empenhos registrados no SICONV: historico completo do convenio (o nucleo
    -- SIAFI so cobre os exercicios do relatorio do Tesouro). E a medida de
    -- empenhado do gold antigo.
    empenhos as (
        select
            nr_convenio,
            count(*) as qtd_empenhos_siconv,
            sum(valor_empenho) as valor_empenhado_siconv
        from {{ ref("empenho") }}
        where nr_convenio in (select nr_convenio from mir)
        group by nr_convenio
    )
```

No `select` final, depois de `d.data_ultimo_desembolso` (com a vírgula antes):

```sql
    coalesce(e.qtd_empenhos_siconv, 0) as qtd_empenhos_siconv,
    coalesce(e.valor_empenhado_siconv, 0) as valor_empenhado_siconv
```

E ao final dos joins:

```sql
left join empenhos as e on e.nr_convenio = c.nr_convenio
```

Acrescentar `empenho` ao comentário do topo do arquivo, que lista o que o modelo conta.

- [ ] **Step 4: Documentar em `models/mir_silver/schema.yml`**

No modelo `convenio_movimento_financeiro`, trocar a entrada de `fornecedor_documento` por estas três:

```yaml
      - name: fornecedor_documento
        description: >
          CNPJ do fornecedor (14 digitos) ou CPF mascarado como o SICONV publica
          (***12345***). Preenchido so em pagamento a fornecedor.
      - name: fornecedor_tipo
        description: "PJ (CNPJ), PF (CPF mascarado) ou nulo quando o documento nao tem formato valido."
        tests:
          - accepted_values:
              values: ["PF", "PJ"]
      - name: fornecedor_chave
        description: >
          Chave do fornecedor: o CNPJ para PJ; documento mascarado + '|' + nome
          para PF (os digitos visiveis colidem entre pessoas). Nula sem tipo.
```

No modelo `convenio_contagens`, acrescentar ao final das colunas:

```yaml
      - name: qtd_empenhos_siconv
        description: "Quantidade de empenhos registrados no SICONV para o convenio."
      - name: valor_empenhado_siconv
        description: >
          Soma dos empenhos registrados no SICONV (historico completo). O nucleo
          execucao_ne so cobre os exercicios do relatorio do Tesouro.
```

- [ ] **Step 5: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt nos 2 modelos e no teste.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s convenio_movimento_financeiro convenio_contagens`
Expected: `ERROR=0` e `WARN=0`.

- [ ] **Step 6: Conferir que nada mais mudou**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At \
 -c "select md5(string_agg(concat_ws('|', id_movimento, nr_convenio, tipo_movimento, data_movimento, valor, valor_bloqueado, documento_referencia), ',' order by id_movimento)) from mir_silver.convenio_movimento_financeiro" \
 -c "select md5(string_agg(concat_ws('|', nr_convenio, qtd_metas, valor_metas, data_fim_primeira_meta, qtd_licitacoes, valor_licitado, data_ultimo_desembolso), ',' order by nr_convenio)) from mir_silver.convenio_contagens" \
 -c "select coalesce(fornecedor_tipo,'-'), count(*), count(distinct fornecedor_chave), sum(valor) from mir_silver.convenio_movimento_financeiro where tipo_movimento = 'Pagamento a fornecedor' group by 1 order by 1" \
 -c "select sum(qtd_empenhos_siconv), sum(valor_empenhado_siconv) from mir_silver.convenio_contagens"
```
Expected:
- `3f5ab2ab46b09e69296502857ff71463` (movimentos iguais aos de antes, fora as colunas de fornecedor);
- `53200a0cf8d36d52c5dd85af1623c24c` (contagens iguais, fora as colunas novas);
- `-|2586|0|7914906.56`, `PF|6608|2416|6753313.10`, `PJ|11717|3003|85661265.06`;
- `905|143870442.64`.

- [ ] **Step 7: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/models/mir_silver/convenio_movimento_financeiro.sql $M/models/mir_silver/convenio_contagens.sql $M/models/mir_silver/schema.yml $M/tests/mir_silver/convenio_contagens_ids_unicos.sql"
git add -- $P
git commit -m "feat(dbt/mir): fornecedor com CPF mascarado e empenhos do SICONV em mir_silver" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 2: Silver — `emenda_ne` (emenda e parlamentar de cada NE)

**Files:**
- Create: `models/mir_silver/emenda_ne.sql`
- Modify: `models/mir_silver/schema.yml` (acrescentar ao final)
- Test: `tests/mir_silver/emenda_ne_cobertura.sql`
- Test: `tests/mir_silver/emenda_ne_autor_sem_cadastro.sql`

**Interfaces:**
- Consumes: `ref("execucao_ne")` (`ne_ccor`, `codigo_emenda`, `data_emissao`, `inscricao_rap`), `ref("tg_emendas")` (`ne_ccor`, `autor_emendas_orcamento_descricao`, `autor_emendas_orcamento_nome`), `ref("parlamentares_historico")` (`chave_join_nome`, `id_parlamentar integer`, `cargo_parlamentar`, `sigla_partido`, `data_filiacao`/`data_desfiliacao timestamptz`), macro existente `name_formater`.
- Produces: `mir_silver.emenda_ne`, PK `ne_ccor`. Colunas: `ne_ccor text`, `codigo_emenda text`, `emenda_descricao text`, `autor_nome text`, `data_emissao_ne date`, `id_parlamentar integer` (nulo sem cadastro), `cargo_parlamentar text`, `sigla_partido text`, `prioridade_match integer` (1, 2 ou 3). A Tarefa 4 usa este modelo em `dim_emenda`, e a Tarefa 6 na FK `sk_parlamentar`.

Regra (a mesma do `emendas_partidos`, que será removido na etapa 5): o autor é achado pelo nome em `parlamentares_historico`. Prioridade 1 = filiação vigente na data de emissão da NE; 2 = nome encontrado, mas nenhuma filiação cobre a data (fica a mais próxima); 3 = nome não encontrado. Diferença deliberada: a filiação sem data de fim é tratada como `infinity`, e não como `current_date` (a silver não depende da data de hoje). Medido: o partido resultante é igual ao do `emendas_partidos` nas 221 NEs.

- [ ] **Step 1: Escrever os testes singulares**

Criar `tests/mir_silver/emenda_ne_cobertura.sql`:

```sql
-- Falha se alguma NE de emenda do nucleo faltar em emenda_ne ou vier com outra
-- emenda.
with
    nucleo as (
        select distinct ne_ccor, codigo_emenda
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
    )

select n.ne_ccor, n.codigo_emenda, e.codigo_emenda as codigo_emenda_ne
from nucleo as n
left join {{ ref("emenda_ne") }} as e on e.ne_ccor = n.ne_ccor
where e.codigo_emenda is distinct from n.codigo_emenda
```

Criar `tests/mir_silver/emenda_ne_autor_sem_cadastro.sql`:

```sql
{{ config(severity="warn", warn_if=">4") }}

-- Aviso (nao bloqueia a DAG): autores de emenda cujo nome nao foi encontrado em
-- parlamentares_historico (grafia divergente). As NEs deles ficam com
-- parlamentar Nao identificado no gold. Linha de base em 2026-09-29: 4 autores
-- (Augusto Puppio, Guilherme Boulos, Paulao, Reginete Bispo); o aviso so
-- dispara se aparecer um quinto.
select autor_nome, count(*) as qtd_nes
from {{ ref("emenda_ne") }}
where prioridade_match = 3
group by autor_nome
```

- [ ] **Step 2: Criar `models/mir_silver/emenda_ne.sql`**

```sql
{{ config(materialized="table") }}

-- NEs de emenda, uma linha por NE: a emenda (tg_emendas) e o parlamentar autor
-- com o partido vigente na data de emissao da NE. O parlamentar e achado pelo
-- nome em parlamentares_historico, com as prioridades do emendas_partidos:
-- 1 = filiacao vigente na data de emissao; 2 = nome encontrado, mas nenhuma
-- filiacao cobre a data (fica a mais proxima); 3 = nome nao encontrado
-- (parlamentar nulo). Filiacao sem data de fim vale como aberta (infinity),
-- sem depender da data de hoje.
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

    autores as (
        select distinct
            ne_ccor,
            autor_emendas_orcamento_descricao as emenda_descricao,
            autor_emendas_orcamento_nome as autor_nome,
            {{ name_formater("autor_emendas_orcamento_nome") }} as chave_join_nome
        from {{ ref("tg_emendas") }}
    ),

    candidatos as (
        select
            n.ne_ccor,
            n.codigo_emenda,
            n.data_emissao_ne,
            a.emenda_descricao,
            a.autor_nome,
            p.id_parlamentar,
            p.cargo_parlamentar,
            p.sigla_partido,
            case
                when p.id_parlamentar is null
                then 3
                when
                    n.data_emissao_ne >= p.data_filiacao::date
                    and n.data_emissao_ne
                    <= coalesce(p.data_desfiliacao::date, 'infinity'::date)
                then 1
                else 2
            end as prioridade_match,
            least(
                abs(n.data_emissao_ne - p.data_filiacao::date),
                abs(n.data_emissao_ne - p.data_desfiliacao::date)
            ) as distancia_dias
        from nes as n
        inner join autores as a on a.ne_ccor = n.ne_ccor
        left join
            {{ ref("parlamentares_historico") }} as p
            on p.chave_join_nome = a.chave_join_nome
    )

select distinct on (ne_ccor)
    ne_ccor,
    codigo_emenda,
    emenda_descricao,
    autor_nome,
    data_emissao_ne,
    id_parlamentar,
    cargo_parlamentar,
    sigla_partido,
    prioridade_match
from candidatos
order by
    ne_ccor, prioridade_match, distancia_dias nulls last, id_parlamentar, sigla_partido
```

- [ ] **Step 3: Documentar em `models/mir_silver/schema.yml` (acrescentar ao final)**

```yaml
  - name: emenda_ne
    description: >
      NEs de emenda, uma linha por NE: a emenda (tg_emendas) e o parlamentar
      autor com o partido vigente na data de emissao da NE, pelas prioridades do
      emendas_partidos (1 = filiacao vigente; 2 = nome encontrado fora do
      periodo, filiacao mais proxima; 3 = nome nao encontrado).
    columns:
      - name: ne_ccor
        description: "Numero completo da nota de empenho."
        tests:
          - unique
          - not_null
      - name: codigo_emenda
        description: "Codigo da emenda (tg_emendas.autor_emendas_orcamento): ano (4) + autor (4) + numero (4)."
        tests:
          - not_null
      - name: emenda_descricao
        description: "Texto do autor e numero da emenda, como vem do Tesouro (ex.: FERNANDO MINEIRO / EMENDA 13)."
      - name: autor_nome
        description: "Nome do autor extraido da descricao."
      - name: data_emissao_ne
        description: "Primeira data de emissao da NE que nao e inscricao de restos a pagar."
        tests:
          - not_null
      - name: id_parlamentar
        description: "Parlamentar em parlamentares_historico. Nulo quando o nome nao foi encontrado."
      - name: cargo_parlamentar
        description: "Deputado ou Senador."
      - name: sigla_partido
        description: "Partido do parlamentar na data de emissao da NE."
      - name: prioridade_match
        description: "1 = filiacao vigente na data; 2 = filiacao mais proxima; 3 = nome nao encontrado."
        tests:
          - not_null
          - accepted_values:
              values: [1, 2, 3]
              quote: false
```

- [ ] **Step 4: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt no modelo e nos 2 testes.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s emenda_ne`
Expected: `ERROR=0` e `WARN=0` (o aviso de autor sem cadastro fica abaixo do limite de 4).

- [ ] **Step 5: Conferir contra a linha de base e o modelo antigo**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At \
 -c "select prioridade_match, count(*), count(distinct codigo_emenda) from mir_silver.emenda_ne group by 1 order by 1" \
 -c "select count(*) filter (where e.partido is distinct from n.sigla_partido) from mir_silver.emenda_ne as n join (select distinct on (ne_ccor) ne_ccor, partido from emendas.emendas_partidos order by ne_ccor, emissao_dia nulls last) as e using (ne_ccor)"
```
Expected: `1|210|82` e `3|11|4`; divergências de partido com `emendas_partidos`: `0`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/models/mir_silver/emenda_ne.sql $M/models/mir_silver/schema.yml $M/tests/mir_silver/emenda_ne_cobertura.sql $M/tests/mir_silver/emenda_ne_autor_sem_cadastro.sql"
git add -- $P
git commit -m "feat(dbt/mir): emenda e parlamentar de cada NE em mir_silver" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 3: Base do gold — schema, macros de chave, teste do membro `-1`, seed e `dim_tempo`

**Files:**
- Modify: `dbt_project.yml`
- Create: `macros/mir_gold/chaves.sql`
- Create: `macros/mir_gold/dim_tempo.sql`
- Create: `tests/generic/membro_nao_identificado.sql`
- Create: `seeds/uf_regiao.csv`
- Modify: `seeds/schema.yml`
- Create: `models/mir_convenios/dim_tempo.sql`
- Create: `models/mir_convenios/schema.yml`

**Interfaces:**
- Produces (usadas por todas as tarefas seguintes):
  - `{{ surrogate_key(["col1", "col2"]) }}` → `bigint`, md5 das colunas (convertidas para texto, nulo vira `''`, separadas por `|`). A dimensão e a fato chamam com as **mesmas colunas, na mesma ordem e com os mesmos valores de texto**.
  - `{{ fk(["col1", ...]) }}` → `-1` quando a **primeira** coluna é nula; senão `surrogate_key` das colunas. Usar nas fatos.
  - `{{ sk_tempo("<expressao date>") }}` → `AAAAMMDD` como `bigint`, `-1` quando nula.
  - teste genérico `membro_nao_identificado` (em coluna `sk_*` de dimensão): falha se não há linha com valor `-1`.
  - seed `uf_regiao` (`uf`, `nome_uf`, `regiao`), 27 linhas.
  - `mir_convenios.dim_tempo` (`sk_tempo`, `data`, `ano`, `semestre`, `trimestre`, `mes`, `nome_mes`, `ano_mes`), 2000-01-01 a 2040-12-31 + `-1`.

- [ ] **Step 1: Configurar o schema do mart em `dbt_project.yml`**

Depois do bloco `mir_silver:` em `models: mir:`, acrescentar:

```yaml
    mir_convenios:
      +materialized: table
      +schema: mir_convenios
```

- [ ] **Step 2: Criar `macros/mir_gold/chaves.sql`**

```sql
{#
    Chaves do gold (spec §4). A chave substituta e um bigint derivado da chave
    natural por md5: estavel entre execucoes, sem sequencia. Dimensao e fato
    calculam a chave com a mesma macro, entao a fato nao precisa de join com a
    dimensao; o teste relationships garante que a chave existe.
#}
{% macro surrogate_key(colunas) -%}
    ('x' || substr(md5(concat_ws('|'
    {%- for c in colunas %}, coalesce(({{ c }})::text, ''){% endfor -%}
    )), 1, 16))::bit(64)::bigint
{%- endmacro %}

{# FK de fato: -1 (Nao identificado) quando a primeira coluna da chave e nula. #}
{% macro fk(colunas) -%}
    case
        when ({{ colunas[0] }}) is null
        then -1::bigint
        else {{ surrogate_key(colunas) }}
    end
{%- endmacro %}

{# Chave da dim_tempo: a data como AAAAMMDD; -1 quando a data e nula. #}
{% macro sk_tempo(data) -%}
    coalesce(to_char({{ data }}, 'YYYYMMDD')::bigint, -1::bigint)
{%- endmacro %}
```

- [ ] **Step 3: Criar o teste genérico `tests/generic/membro_nao_identificado.sql`**

```sql
{#
    Falha se a dimensao nao tem o membro -1 (Nao identificado), para onde vao
    as FKs nulas das fatos.
#}
{% test membro_nao_identificado(model, column_name) %}
    select 1 as membro_ausente
    where not exists (select 1 from {{ model }} where {{ column_name }} = -1)
{% endtest %}
```

- [ ] **Step 4: Criar a seed `seeds/uf_regiao.csv`**

```csv
uf,nome_uf,regiao
AC,Acre,Norte
AL,Alagoas,Nordeste
AM,Amazonas,Norte
AP,Amapá,Norte
BA,Bahia,Nordeste
CE,Ceará,Nordeste
DF,Distrito Federal,Centro-Oeste
ES,Espírito Santo,Sudeste
GO,Goiás,Centro-Oeste
MA,Maranhão,Nordeste
MG,Minas Gerais,Sudeste
MS,Mato Grosso do Sul,Centro-Oeste
MT,Mato Grosso,Centro-Oeste
PA,Pará,Norte
PB,Paraíba,Nordeste
PE,Pernambuco,Nordeste
PI,Piauí,Nordeste
PR,Paraná,Sul
RJ,Rio de Janeiro,Sudeste
RN,Rio Grande do Norte,Nordeste
RO,Rondônia,Norte
RR,Roraima,Norte
RS,Rio Grande do Sul,Sul
SC,Santa Catarina,Sul
SE,Sergipe,Nordeste
SP,São Paulo,Sudeste
TO,Tocantins,Norte
```

E acrescentar ao final de `seeds/schema.yml`:

```yaml
  - name: uf_regiao
    description: "Unidades da federacao com nome e regiao; alimenta dim_localidade."
    config:
      column_types:
        uf: text
        nome_uf: text
        regiao: text
    columns:
      - name: uf
        tests:
          - unique
          - not_null
```

- [ ] **Step 5: Criar `macros/mir_gold/dim_tempo.sql`**

```sql
{#
    Dimensao de tempo compartilhada pelos marts (spec §4 e §6): um dia por
    linha, de inicio a fim, mais o membro -1 para fatos sem data.
#}
{% macro dim_tempo(inicio="2000-01-01", fim="2040-12-31") %}
    select
        {{ sk_tempo("d::date") }} as sk_tempo,
        d::date as data,
        extract(year from d)::integer as ano,
        case when extract(month from d) <= 6 then 1 else 2 end as semestre,
        extract(quarter from d)::integer as trimestre,
        extract(month from d)::integer as mes,
        (
            array[
                'Janeiro',
                'Fevereiro',
                'Março',
                'Abril',
                'Maio',
                'Junho',
                'Julho',
                'Agosto',
                'Setembro',
                'Outubro',
                'Novembro',
                'Dezembro'
            ]
        )[extract(month from d)::integer] as nome_mes,
        to_char(d, 'YYYY-MM') as ano_mes
    from generate_series('{{ inicio }}'::date, '{{ fim }}'::date, interval '1 day') as d

    union all

    select
        -1::bigint,
        null::date,
        null::integer,
        null::integer,
        null::integer,
        null::integer,
        'Não identificado',
        'Não identificado'
{% endmacro %}
```

- [ ] **Step 6: Criar o modelo `models/mir_convenios/dim_tempo.sql`**

```sql
{{ dim_tempo() }}
```

- [ ] **Step 7: Criar `models/mir_convenios/schema.yml`**

```yaml
version: 2

models:
  - name: dim_tempo
    description: "Calendario diario de 2000 a 2040; sk_tempo = AAAAMMDD; -1 = sem data."
    columns:
      - name: sk_tempo
        description: "Data como AAAAMMDD (bigint); -1 = Nao identificado."
        tests:
          - unique
          - not_null
          - membro_nao_identificado
      - name: data
        description: "Dia."
      - name: ano_mes
        description: "Ano e mes (AAAA-MM), para eixos mensais no Power BI."
```

- [ ] **Step 8: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt em `macros/mir_gold/`, `tests/generic/membro_nao_identificado.sql` e `models/mir_convenios/dim_tempo.sql`.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s uf_regiao dim_tempo`
Expected: `ERROR=0` e `WARN=0` (seed + modelo + testes).

- [ ] **Step 9: Conferir**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At \
 -c "select count(*), min(data), max(data), count(*) filter (where sk_tempo = -1) from mir_convenios.dim_tempo" \
 -c "select sk_tempo, nome_mes, ano_mes, semestre, trimestre from mir_convenios.dim_tempo where data = '2024-08-15'" \
 -c "select count(*) from mir.uf_regiao"
```
Expected: `14977|2000-01-01|2040-12-31|1`; `20240815|Agosto|2024-08|2|3`; `27`.

(A seed vai para o schema padrão do target, `mir`, como as outras seeds do projeto.)

- [ ] **Step 10: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/dbt_project.yml $M/macros/mir_gold/chaves.sql $M/macros/mir_gold/dim_tempo.sql $M/tests/generic/membro_nao_identificado.sql $M/seeds/uf_regiao.csv $M/seeds/schema.yml $M/models/mir_convenios/dim_tempo.sql $M/models/mir_convenios/schema.yml"
git add -- $P
git commit -m "feat(dbt/mir): base do gold mir_convenios com chaves, dim_tempo e seed de UF" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 4: Dimensões compartilhadas — orçamento, emenda e parlamentar

**Files:**
- Create: `macros/mir_gold/dim_unidade_gestora.sql`, `dim_acao_orcamentaria.sql`, `dim_natureza_despesa.sql`, `dim_fonte_recurso.sql`, `dim_emenda.sql`, `dim_parlamentar.sql`
- Create: `models/mir_convenios/dim_unidade_gestora.sql`, `dim_acao_orcamentaria.sql`, `dim_natureza_despesa.sql`, `dim_fonte_recurso.sql`, `dim_emenda.sql`, `dim_parlamentar.sql` (uma linha cada: `{{ <nome_da_macro>() }}`)
- Modify: `models/mir_convenios/schema.yml` (acrescentar)

**Interfaces:**
- Consumes: `surrogate_key` (Tarefa 3); `ref("execucao_ne")`; `ref("emenda_ne")` (Tarefa 2); `ref("parlamentares_historico")`.
- Produces (chave natural → como a fato calcula a FK na Tarefa 6):
  - `dim_unidade_gestora.sk_unidade_gestora` ← `fk(["x.ug_responsavel_codigo"])`
  - `dim_acao_orcamentaria.sk_acao_orcamentaria` ← `fk(["x.ptres"])`
  - `dim_natureza_despesa.sk_natureza_despesa` ← `fk(["x.natureza_despesa"])`
  - `dim_fonte_recurso.sk_fonte_recurso` ← `fk(["x.fonte_recursos_detalhada"])`
  - `dim_emenda.sk_emenda` ← `fk(["x.codigo_emenda"])`
  - `dim_parlamentar.sk_parlamentar` ← `fk(["e.id_parlamentar", "e.cargo_parlamentar", "e.sigla_partido"])` (de `emenda_ne`)

As dimensões orçamentárias leem o núcleo inteiro (`execucao_ne`), não só as linhas de convênio: são pequenas (70 UGs, 142 PTRES) e assim a mesma macro serve aos três marts. Chaves naturais estáveis no dump (cada PTRES, natureza, fonte e UG tem um só conjunto de atributos); o `distinct on ... order by dt_ingest desc` garante uma linha se a origem mudar um nome.

- [ ] **Step 1: Criar as macros**

`macros/mir_gold/dim_unidade_gestora.sql`:

```sql
{# Unidade gestora responsavel das NEs do nucleo. #}
{% macro dim_unidade_gestora() %}
    select {{ surrogate_key(["codigo_ug"]) }} as sk_unidade_gestora, u.*
    from
        (
            select distinct on (ug_responsavel_codigo)
                ug_responsavel_codigo as codigo_ug, ug_responsavel_nome as nome_ug
            from {{ ref("execucao_ne") }}
            order by ug_responsavel_codigo, dt_ingest desc
        ) as u

    union all

    select -1::bigint, '-1', 'Não identificado'
{% endmacro %}
```

`macros/mir_gold/dim_acao_orcamentaria.sql`:

```sql
{#
    Classificacao programatica no grao do PTRES: programa, acao, plano
    orcamentario, funcao e subfuncao (so os codigos de funcao e subfuncao; a
    origem nao traz os nomes).
#}
{% macro dim_acao_orcamentaria() %}
    select {{ surrogate_key(["ptres"]) }} as sk_acao_orcamentaria, a.*
    from
        (
            select distinct on (ptres)
                ptres,
                programa_governo as codigo_programa,
                programa_governo_descricao as programa,
                acao_governo as codigo_acao,
                acao_governo_descricao as acao,
                plano_orcamentario_codigo_po as codigo_plano_orcamentario,
                plano_orcamentario_nome as plano_orcamentario,
                plano_orcamentario_codigo_funcao as codigo_funcao,
                plano_orcamentario_codigo_subfuncao as codigo_subfuncao,
                plano_orcamentario_codigo_uo as codigo_uo
            from {{ ref("execucao_ne") }}
            order by ptres, dt_ingest desc
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
    elemento). A modalidade de aplicacao sai dos digitos 3 e 4.
#}
{% macro dim_natureza_despesa() %}
    select {{ surrogate_key(["natureza_despesa"]) }} as sk_natureza_despesa, n.*
    from
        (
            select distinct on (natureza_despesa)
                natureza_despesa,
                natureza_despesa_descricao,
                grupo_despesa as codigo_gnd,
                grupo_despesa_desc as gnd,
                substr(natureza_despesa, 3, 2) as codigo_modalidade_aplicacao
            from {{ ref("execucao_ne") }}
            order by natureza_despesa, dt_ingest desc
        ) as n

    union all

    select -1::bigint, '-1', 'Não identificado', null, 'Não identificado', null
{% endmacro %}
```

`macros/mir_gold/dim_fonte_recurso.sql`:

```sql
{# Fonte de recursos detalhada das NEs do nucleo. #}
{% macro dim_fonte_recurso() %}
    select {{ surrogate_key(["codigo_fonte"]) }} as sk_fonte_recurso, f.*
    from
        (
            select distinct on (fonte_recursos_detalhada)
                fonte_recursos_detalhada as codigo_fonte,
                fonte_recursos_detalhada_descricao as fonte
            from {{ ref("execucao_ne") }}
            order by fonte_recursos_detalhada, dt_ingest desc
        ) as f

    union all

    select -1::bigint, '-1', 'Não identificado'
{% endmacro %}
```

`macros/mir_gold/dim_emenda.sql`:

```sql
{#
    Emenda parlamentar. O codigo tem 12 digitos: ano (4) + autor (4) + numero
    (4), ex.: 202443740013 = emenda 13 de 2024.
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
            from {{ ref("emenda_ne") }}
            order by codigo_emenda, ne_ccor
        ) as e

    union all

    select -1::bigint, '-1', null, null, 'Não identificado', 'Não identificado'
{% endmacro %}
```

`macros/mir_gold/dim_parlamentar.sql`:

```sql
{#
    Parlamentar em SCD2 no grao parlamentar x cargo x partido (spec §4):
    valido_de = primeira filiacao ao partido, valido_ate = ultima desfiliacao
    (nula enquanto a filiacao esta aberta). Atributos descritivos vem da carga
    mais recente. O e-mail nao entra no gold.
#}
{% macro dim_parlamentar() %}
    select
        {{ surrogate_key(["id_parlamentar", "cargo_parlamentar", "sigla_partido"]) }}
        as sk_parlamentar,
        p.*
    from
        (
            select
                id_parlamentar,
                cargo_parlamentar,
                sigla_partido,
                (array_agg(nome_parlamentar order by dt_ingest desc))[1] as nome_parlamentar,
                (array_agg(uf_parlamentar order by dt_ingest desc))[1] as uf_parlamentar,
                (array_agg(url_foto order by dt_ingest desc))[1] as url_foto,
                (array_agg(url_logo_partido order by dt_ingest desc))[1] as url_logo_partido,
                min(data_filiacao)::date as valido_de,
                case
                    when bool_or(data_desfiliacao is null)
                    then null
                    else max(data_desfiliacao)::date
                end as valido_ate
            from {{ ref("parlamentares_historico") }}
            group by id_parlamentar, cargo_parlamentar, sigla_partido
        ) as p

    union all

    select
        -1::bigint,
        null,
        'Não identificado',
        'Não identificado',
        'Não identificado',
        null,
        null,
        null,
        null,
        null
{% endmacro %}
```

- [ ] **Step 2: Criar os 6 modelos**

Cada arquivo em `models/mir_convenios/` tem uma linha só, com a macro do mesmo nome:

```sql
{{ dim_unidade_gestora() }}
```
```sql
{{ dim_acao_orcamentaria() }}
```
```sql
{{ dim_natureza_despesa() }}
```
```sql
{{ dim_fonte_recurso() }}
```
```sql
{{ dim_emenda() }}
```
```sql
{{ dim_parlamentar() }}
```

- [ ] **Step 3: Documentar em `models/mir_convenios/schema.yml` (acrescentar em `models:`)**

```yaml
  - name: dim_unidade_gestora
    description: "UG responsavel das NEs (macro compartilhada dim_unidade_gestora)."
    columns:
      - name: sk_unidade_gestora
        tests: [unique, not_null, membro_nao_identificado]
      - name: codigo_ug
        tests: [unique, not_null]

  - name: dim_acao_orcamentaria
    description: "Classificacao programatica no grao do PTRES (macro compartilhada)."
    columns:
      - name: sk_acao_orcamentaria
        tests: [unique, not_null, membro_nao_identificado]
      - name: ptres
        tests: [unique, not_null]

  - name: dim_natureza_despesa
    description: "Natureza de despesa, GND e modalidade de aplicacao (macro compartilhada)."
    columns:
      - name: sk_natureza_despesa
        tests: [unique, not_null, membro_nao_identificado]
      - name: natureza_despesa
        tests: [unique, not_null]

  - name: dim_fonte_recurso
    description: "Fonte de recursos detalhada (macro compartilhada)."
    columns:
      - name: sk_fonte_recurso
        tests: [unique, not_null, membro_nao_identificado]
      - name: codigo_fonte
        tests: [unique, not_null]

  - name: dim_emenda
    description: "Emenda parlamentar: codigo, ano, numero e autor (macro compartilhada)."
    columns:
      - name: sk_emenda
        tests: [unique, not_null, membro_nao_identificado]
      - name: codigo_emenda
        tests: [unique, not_null]

  - name: dim_parlamentar
    description: >
      Parlamentar x cargo x partido (SCD2), com valido_de e valido_ate. A fato
      aponta para o partido vigente na data de emissao da NE (mir_silver.emenda_ne).
    columns:
      - name: sk_parlamentar
        tests: [unique, not_null, membro_nao_identificado]
```

- [ ] **Step 4: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt nas 6 macros e nos 6 modelos.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s dim_unidade_gestora dim_acao_orcamentaria dim_natureza_despesa dim_fonte_recurso dim_emenda dim_parlamentar`
Expected: `ERROR=0` e `WARN=0`.

- [ ] **Step 5: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "
select 'ug', count(*) from mir_convenios.dim_unidade_gestora union all
select 'acao', count(*) from mir_convenios.dim_acao_orcamentaria union all
select 'natureza', count(*) from mir_convenios.dim_natureza_despesa union all
select 'fonte', count(*) from mir_convenios.dim_fonte_recurso union all
select 'emenda', count(*) from mir_convenios.dim_emenda union all
select 'parlamentar', count(*) from mir_convenios.dim_parlamentar" \
 -c "select ano, numero, emenda_descricao from mir_convenios.dim_emenda where codigo_emenda = '202443740013'"
```
Expected: `ug|71`, `acao|143`, `natureza|40`, `fonte|34`, `emenda|87`, `parlamentar|1242`; `2024|13|FERNANDO MINEIRO / EMENDA 13`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P=""
for d in dim_unidade_gestora dim_acao_orcamentaria dim_natureza_despesa dim_fonte_recurso dim_emenda dim_parlamentar; do
  P="$P $M/macros/mir_gold/$d.sql $M/models/mir_convenios/$d.sql"
done
P="$P $M/models/mir_convenios/schema.yml"
git add -- $P
git commit -m "feat(dbt/mir): dimensoes compartilhadas de orcamento, emenda e parlamentar" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 5: Dimensões do convênio — convênio, convenente, localidade e fornecedor

**Files:**
- Create: `models/mir_convenios/dim_convenio.sql`, `dim_convenente.sql`, `dim_localidade.sql`, `dim_fornecedor.sql`
- Modify: `models/mir_convenios/schema.yml` (acrescentar)

**Interfaces:**
- Consumes: `surrogate_key` (Tarefa 3); seed `uf_regiao` (Tarefa 3); `ref("convenio_mir")`, `ref("convenio_evento")`, `ref("convenio_contagens")` (`data_fim_primeira_meta`), `ref("convenio_movimento_financeiro")` (`fornecedor_chave`, `fornecedor_documento`, `fornecedor_nome`, `fornecedor_tipo` da Tarefa 1).
- Produces (chave natural → como as fatos calculam a FK nas Tarefas 6 e 7):
  - `dim_convenio.sk_convenio` ← `fk(["<nr_convenio>"])`
  - `dim_convenente.sk_convenente` ← `fk(["c.convenente_documento"])`
  - `dim_localidade.sk_localidade` ← `fk(["coalesce(c.cod_municipio_ibge, 'UF-' || c.uf)"])`
  - `dim_fornecedor.sk_fornecedor` ← `fk(["m.fornecedor_chave"])`

`vigente` e `meta_expirada` são calculados aqui contra `current_date`, exposto em `data_referencia` (decisão do usuário: a silver guarda datas; o gold calcula a marcação com a data de referência explícita). Medido em 2026-09-29: 134 convênios vigentes, 18 inadimplentes, 30 anulados.

- [ ] **Step 1: Criar `models/mir_convenios/dim_convenio.sql`**

```sql
-- Dimensao do convenio: atributos do instrumento, situacao e datas. As
-- marcacoes que dependem da data (vigente, meta expirada) sao calculadas contra
-- data_referencia, a data da carga, exposta na propria dimensao. As marcacoes
-- de inadimplente, rescindido e anulado valem se o convenio passou alguma vez
-- pela situacao (mesma regra do gold antigo).
with
    situacoes as (
        select
            nr_convenio,
            bool_or(situacao = 'INADIMPLENTE') as inadimplente,
            bool_or(situacao = 'CONVENIO_RESCINDIDO') as rescindido,
            bool_or(situacao = 'CONVENIO_ANULADO') as anulado
        from {{ ref("convenio_evento") }}
        where tipo_evento = 'Mudança de situação'
        group by nr_convenio
    )

select
    {{ surrogate_key(["c.nr_convenio"]) }} as sk_convenio,
    c.nr_convenio,
    c.modalidade,
    c.origem_recurso,
    c.complemento_proprio,
    c.objeto,
    c.situacao,
    c.subsituacao,
    c.situacao_publicacao,
    c.instrumento_ativo,
    coalesce(s.inadimplente, false) as inadimplente,
    coalesce(s.rescindido, false) as rescindido,
    coalesce(s.anulado, false) as anulado,
    c.nr_processo,
    c.ug_emitente,
    c.ug_responsavel_codigo,
    c.ug_responsavel_nome,
    c.data_assinatura,
    c.data_publicacao,
    c.data_inicio_vigencia,
    c.data_fim_vigencia,
    c.data_fim_vigencia_original,
    c.data_limite_prestacao_contas,
    k.data_fim_primeira_meta,
    current_date as data_referencia,
    coalesce(c.data_fim_vigencia >= current_date, false) as vigente,
    coalesce(k.data_fim_primeira_meta < current_date, false) as meta_expirada
from {{ ref("convenio_mir") }} as c
left join situacoes as s on s.nr_convenio = c.nr_convenio
left join {{ ref("convenio_contagens") }} as k on k.nr_convenio = c.nr_convenio

union all

select
    -1::bigint,
    '-1',
    'Não identificado',
    'Não identificada',
    false,
    'Não identificado',
    'Não identificado',
    null,
    null,
    null,
    false,
    false,
    false,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    current_date,
    false,
    false
```

- [ ] **Step 2: Criar `models/mir_convenios/dim_convenente.sql`**

```sql
-- Convenente (proponente) dos convenios do MIR, pelo CNPJ. Quando o mesmo CNPJ
-- aparece com nomes diferentes, fica o do convenio assinado mais recentemente.
select {{ surrogate_key(["convenente_documento"]) }} as sk_convenente, c.*
from
    (
        select distinct on (convenente_documento)
            convenente_documento, convenente_nome, convenente_natureza_juridica
        from {{ ref("convenio_mir") }}
        where convenente_documento is not null
        order by convenente_documento, data_assinatura desc nulls last
    ) as c

union all

select -1::bigint, '-1', 'Não identificado', 'Não identificado'
```

- [ ] **Step 3: Criar `models/mir_convenios/dim_localidade.sql`**

```sql
-- Municipio do convenente (codigo IBGE), com UF e regiao. Convenio sem
-- municipio fica numa linha so com a UF (chave 'UF-<sigla>').
with
    locais as (
        select distinct on (chave_localidade) *
        from
            (
                select
                    coalesce(cod_municipio_ibge, 'UF-' || uf) as chave_localidade,
                    cod_municipio_ibge,
                    municipio,
                    uf
                from {{ ref("convenio_mir") }}
                where coalesce(cod_municipio_ibge, uf) is not null
            ) as l
        order by chave_localidade, municipio
    )

select
    {{ surrogate_key(["l.chave_localidade"]) }} as sk_localidade,
    l.chave_localidade,
    l.cod_municipio_ibge,
    coalesce(l.municipio, 'Não informado') as municipio,
    l.uf,
    r.nome_uf,
    r.regiao
from locais as l
left join {{ ref("uf_regiao") }} as r on r.uf = l.uf

union all

select
    -1::bigint,
    '-1',
    null,
    'Não identificado',
    null,
    'Não identificado',
    'Não identificado'
```

- [ ] **Step 4: Criar `models/mir_convenios/dim_fornecedor.sql`**

```sql
-- Fornecedores pagos com recurso dos convenios do MIR. O SICONV ja publica o
-- CPF mascarado; a chave de pessoa fisica e documento mascarado + nome (regra
-- em convenio_movimento_financeiro). Para PJ com nomes diferentes no mesmo
-- CNPJ, fica o nome do pagamento mais recente.
select {{ surrogate_key(["fornecedor_chave"]) }} as sk_fornecedor, f.*
from
    (
        select distinct on (fornecedor_chave)
            fornecedor_chave, fornecedor_documento, fornecedor_nome, fornecedor_tipo
        from {{ ref("convenio_movimento_financeiro") }}
        where fornecedor_chave is not null
        order by fornecedor_chave, data_movimento desc nulls last, id_movimento
    ) as f

union all

select -1::bigint, '-1', null, 'Não identificado', 'Não identificado'
```

- [ ] **Step 5: Documentar em `models/mir_convenios/schema.yml` (acrescentar em `models:`)**

```yaml
  - name: dim_convenio
    description: >
      Convenios, termos de fomento, colaboracao e parceria do MIR: modalidade,
      origem do recurso, situacao, marcacoes e datas. vigente e meta_expirada
      sao calculados contra data_referencia (data da carga).
    columns:
      - name: sk_convenio
        tests: [unique, not_null, membro_nao_identificado]
      - name: nr_convenio
        tests: [unique, not_null]
      - name: origem_recurso
        description: "Emenda, Recurso próprio ou Não identificada (sem NE no relatorio do Tesouro)."
        tests:
          - not_null
          - accepted_values:
              values: ["Emenda", "Recurso próprio", "Não identificada"]
      - name: complemento_proprio
        description: "Instrumento de Emenda que tambem recebeu NE de recurso proprio (complemento ate o minimo legal)."
      - name: data_referencia
        description: "Data da carga, usada para calcular vigente e meta_expirada."
      - name: vigente
        description: "data_fim_vigencia >= data_referencia."
      - name: meta_expirada
        description: "Alguma meta com fim anterior a data_referencia."

  - name: dim_convenente
    description: "Convenente (proponente) pelo CNPJ."
    columns:
      - name: sk_convenente
        tests: [unique, not_null, membro_nao_identificado]
      - name: convenente_documento
        tests: [unique, not_null]

  - name: dim_localidade
    description: "Municipio IBGE do convenente, com UF e regiao; linha so com UF quando falta o municipio."
    columns:
      - name: sk_localidade
        tests: [unique, not_null, membro_nao_identificado]
      - name: chave_localidade
        tests: [unique, not_null]
      - name: uf
        tests:
          - relationships:
              to: ref('uf_regiao')
              field: uf

  - name: dim_fornecedor
    description: >
      Fornecedores pagos pelos convenios. CPF aparece mascarado como o SICONV
      publica; a chave de PF e documento mascarado + nome.
    columns:
      - name: sk_fornecedor
        tests: [unique, not_null, membro_nao_identificado]
      - name: fornecedor_chave
        tests: [unique, not_null]
      - name: fornecedor_tipo
        tests:
          - accepted_values:
              values: ["PF", "PJ", "Não identificado"]
```

- [ ] **Step 6: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt nos 4 modelos.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s dim_convenio dim_convenente dim_localidade dim_fornecedor`
Expected: `ERROR=0` e `WARN=0`.

- [ ] **Step 7: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "
select 'convenio', count(*) from mir_convenios.dim_convenio union all
select 'convenente', count(*) from mir_convenios.dim_convenente union all
select 'localidade', count(*) from mir_convenios.dim_localidade union all
select 'fornecedor', count(*) from mir_convenios.dim_fornecedor union all
select 'localidade sem regiao', count(*) from mir_convenios.dim_localidade where sk_localidade <> -1 and regiao is null union all
select 'origem ' || origem_recurso, count(*) from mir_convenios.dim_convenio where sk_convenio <> -1 group by origem_recurso"
```
Expected: `convenio|644`, `convenente|422`, `localidade|179`, `fornecedor|5420`, `localidade sem regiao|0`, `origem Emenda|189`, `origem Não identificada|418`, `origem Recurso próprio|36`.

- [ ] **Step 8: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir/models/mir_convenios
P="$M/dim_convenio.sql $M/dim_convenente.sql $M/dim_localidade.sql $M/dim_fornecedor.sql $M/schema.yml"
git add -- $P
git commit -m "feat(dbt/mir): dimensoes de convenio, convenente, localidade e fornecedor" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 6: Fatos transacionais e reconciliação

**Files:**
- Create: `models/mir_convenios/fato_execucao_orcamentaria.sql`, `fato_fluxo_financeiro.sql`, `fato_cronograma_desembolso.sql`, `fato_evento_convenio.sql`
- Modify: `models/mir_convenios/schema.yml` (acrescentar)
- Test: `tests/mir_convenios/mir_convenios_reconciliacao.sql`

**Interfaces:**
- Consumes: `fk`, `sk_tempo` (Tarefa 3); todas as dimensões (Tarefas 3–5) via `relationships`; `ref("execucao_ne")`, `ref("convenio_mir")`, `ref("emenda_ne")`, `ref("convenio_movimento_financeiro")`, `ref("convenio_cronograma")`, `ref("convenio_evento")`.
- Produces: as 4 fatos, cada uma com sua chave degenerada única (`id_execucao_ne`, `id_movimento`, `id_parcela`, `id_evento`). A Tarefa 7 soma `fato_execucao_orcamentaria.restos_a_pagar_inscritos_acumulavel`.

- [ ] **Step 1: Escrever o teste de reconciliação**

Criar `tests/mir_convenios/mir_convenios_reconciliacao.sql`:

```sql
-- Falha se alguma fato transacional perder ou duplicar linhas ou valores em
-- relacao a silver de onde vem. A execucao compara com as linhas do nucleo
-- vinculadas a convenios do MIR (convenios de outros orgaos ficam fora).
with
    execucao_silver as (
        select x.*
        from {{ ref("execucao_ne") }} as x
        inner join {{ ref("convenio_mir") }} as c on c.nr_convenio = x.nr_instrumento
        where x.sistema_instrumento = 'SICONV'
    ),

    comparacao as (
        select
            'fato_execucao_orcamentaria' as fato,
            (select count(*) from {{ ref("fato_execucao_orcamentaria") }}) as linhas_fato,
            (select count(*) from execucao_silver) as linhas_silver,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from {{ ref("fato_execucao_orcamentaria") }}
            ) as valor_fato,
            (
                select
                    coalesce(sum(despesas_empenhadas), 0)
                    + coalesce(sum(despesas_liquidadas), 0)
                    + coalesce(sum(despesas_pagas), 0)
                    + coalesce(sum(restos_a_pagar_pagos), 0)
                from execucao_silver
            ) as valor_silver

        union all

        select
            'fato_fluxo_financeiro',
            (select count(*) from {{ ref("fato_fluxo_financeiro") }}),
            (select count(*) from {{ ref("convenio_movimento_financeiro") }}),
            (select coalesce(sum(valor), 0) from {{ ref("fato_fluxo_financeiro") }}),
            (select coalesce(sum(valor), 0) from {{ ref("convenio_movimento_financeiro") }})

        union all

        select
            'fato_cronograma_desembolso',
            (select count(*) from {{ ref("fato_cronograma_desembolso") }}),
            (select count(*) from {{ ref("convenio_cronograma") }}),
            (
                select coalesce(sum(valor_previsto), 0)
                from {{ ref("fato_cronograma_desembolso") }}
            ),
            (select coalesce(sum(valor_previsto), 0) from {{ ref("convenio_cronograma") }})

        union all

        select
            'fato_evento_convenio',
            (select count(*) from {{ ref("fato_evento_convenio") }}),
            (select count(*) from {{ ref("convenio_evento") }}),
            (select coalesce(sum(valor), 0) from {{ ref("fato_evento_convenio") }}),
            (select coalesce(sum(valor), 0) from {{ ref("convenio_evento") }})
    )

select *
from comparacao
where linhas_fato <> linhas_silver or valor_fato <> valor_silver
```

- [ ] **Step 2: Criar `models/mir_convenios/fato_execucao_orcamentaria.sql`**

```sql
-- Execucao orcamentaria dos convenios do MIR: linhas do nucleo execucao_ne
-- vinculadas a um convenio do universo convenio_mir, no mesmo grao (linha do
-- relatorio do Tesouro). Convenios de outros orgaos com NE no relatorio do MIR
-- ficam fora (entram so no mart de Emendas). A emenda e o parlamentar vem da
-- NE; linha de recurso proprio fica com emenda e parlamentar -1.
select
    x.id_execucao_ne,
    x.ne_ccor,
    {{ fk(["x.nr_instrumento"]) }} as sk_convenio,
    {{ sk_tempo("x.data_emissao") }} as sk_tempo,
    {{ fk(["x.ug_responsavel_codigo"]) }} as sk_unidade_gestora,
    {{ fk(["x.ptres"]) }} as sk_acao_orcamentaria,
    {{ fk(["x.natureza_despesa"]) }} as sk_natureza_despesa,
    {{ fk(["x.fonte_recursos_detalhada"]) }} as sk_fonte_recurso,
    {{ fk(["x.codigo_emenda"]) }} as sk_emenda,
    {{ fk(["e.id_parlamentar", "e.cargo_parlamentar", "e.sigla_partido"]) }}
    as sk_parlamentar,
    x.origem_recurso,
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
inner join {{ ref("convenio_mir") }} as c on c.nr_convenio = x.nr_instrumento
left join {{ ref("emenda_ne") }} as e on e.ne_ccor = x.ne_ccor
where x.sistema_instrumento = 'SICONV'
```

- [ ] **Step 3: Criar `models/mir_convenios/fato_fluxo_financeiro.sql`**

```sql
-- Movimentos financeiros dos convenios (desembolso, contrapartida, desbloqueio,
-- pagamento a fornecedor, tributo), um por linha. Fornecedor -1 nos movimentos
-- que nao sao pagamento e nos pagamentos sem documento valido; tempo -1 nos
-- tributos sem data na origem.
select
    m.id_movimento,
    {{ fk(["m.nr_convenio"]) }} as sk_convenio,
    {{ sk_tempo("m.data_movimento") }} as sk_tempo,
    {{ fk(["m.fornecedor_chave"]) }} as sk_fornecedor,
    m.tipo_movimento,
    m.documento_referencia,
    m.valor,
    m.valor_bloqueado
from {{ ref("convenio_movimento_financeiro") }} as m
```

- [ ] **Step 4: Criar `models/mir_convenios/fato_cronograma_desembolso.sql`**

```sql
-- Parcelas previstas no cronograma de desembolso, ligadas ao mes previsto
-- (primeiro dia do mes).
select
    c.id_parcela,
    {{ fk(["c.nr_convenio"]) }} as sk_convenio,
    {{ sk_tempo("c.data_prevista") }} as sk_tempo,
    c.nr_parcela,
    c.responsavel,
    c.valor_previsto
from {{ ref("convenio_cronograma") }} as c
```

- [ ] **Step 5: Criar `models/mir_convenios/fato_evento_convenio.sql`**

```sql
-- Eventos administrativos dos convenios (mudanca de situacao, aditivo,
-- prorrogacao, solicitacoes), um por linha. quantidade = 1 permite contar
-- eventos com soma no Power BI.
select
    e.id_evento,
    {{ fk(["e.nr_convenio"]) }} as sk_convenio,
    {{ sk_tempo("e.data_evento") }} as sk_tempo,
    e.tipo_evento,
    e.situacao,
    e.descricao,
    1 as quantidade,
    e.valor,
    e.valor_aprovado,
    e.dias,
    e.data_fim_nova
from {{ ref("convenio_evento") }} as e
```

- [ ] **Step 6: Documentar em `models/mir_convenios/schema.yml` (acrescentar em `models:`)**

```yaml
  - name: fato_execucao_orcamentaria
    description: >
      Execucao orcamentaria (SIAFI) dos convenios do MIR, no grao da linha do
      relatorio do Tesouro. Some restos_a_pagar_inscritos_acumulavel entre
      exercicios; restos_a_pagar_inscritos inclui as reinscricoes (saldo do
      mesmo dinheiro) e so serve para o saldo de um exercicio.
    columns:
      - name: id_execucao_ne
        tests: [unique, not_null]
      - name: sk_convenio
        tests:
          - not_null
          - relationships: {to: ref('dim_convenio'), field: sk_convenio}
      - name: sk_tempo
        tests:
          - not_null
          - relationships: {to: ref('dim_tempo'), field: sk_tempo}
      - name: sk_unidade_gestora
        tests:
          - not_null
          - relationships: {to: ref('dim_unidade_gestora'), field: sk_unidade_gestora}
      - name: sk_acao_orcamentaria
        tests:
          - not_null
          - relationships: {to: ref('dim_acao_orcamentaria'), field: sk_acao_orcamentaria}
      - name: sk_natureza_despesa
        tests:
          - not_null
          - relationships: {to: ref('dim_natureza_despesa'), field: sk_natureza_despesa}
      - name: sk_fonte_recurso
        tests:
          - not_null
          - relationships: {to: ref('dim_fonte_recurso'), field: sk_fonte_recurso}
      - name: sk_emenda
        tests:
          - not_null
          - relationships: {to: ref('dim_emenda'), field: sk_emenda}
      - name: sk_parlamentar
        tests:
          - not_null
          - relationships: {to: ref('dim_parlamentar'), field: sk_parlamentar}

  - name: fato_fluxo_financeiro
    description: "Movimentos financeiros dos convenios; tipo_movimento degenerado."
    columns:
      - name: id_movimento
        tests: [unique, not_null]
      - name: sk_convenio
        tests:
          - not_null
          - relationships: {to: ref('dim_convenio'), field: sk_convenio}
      - name: sk_tempo
        tests:
          - not_null
          - relationships: {to: ref('dim_tempo'), field: sk_tempo}
      - name: sk_fornecedor
        tests:
          - not_null
          - relationships: {to: ref('dim_fornecedor'), field: sk_fornecedor}

  - name: fato_cronograma_desembolso
    description: "Parcelas previstas de desembolso; responsavel degenerado."
    columns:
      - name: id_parcela
        tests: [unique, not_null]
      - name: sk_convenio
        tests:
          - not_null
          - relationships: {to: ref('dim_convenio'), field: sk_convenio}
      - name: sk_tempo
        tests:
          - not_null
          - relationships: {to: ref('dim_tempo'), field: sk_tempo}

  - name: fato_evento_convenio
    description: "Eventos administrativos dos convenios; tipo_evento e situacao degenerados."
    columns:
      - name: id_evento
        tests: [unique, not_null]
      - name: sk_convenio
        tests:
          - not_null
          - relationships: {to: ref('dim_convenio'), field: sk_convenio}
      - name: sk_tempo
        tests:
          - not_null
          - relationships: {to: ref('dim_tempo'), field: sk_tempo}
```

- [ ] **Step 7: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt nos 4 modelos e no teste.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s fato_execucao_orcamentaria fato_fluxo_financeiro fato_cronograma_desembolso fato_evento_convenio`
Expected: `ERROR=0` e `WARN=0` (inclui `mir_convenios_reconciliacao`, que só roda quando os 4 pais estão selecionados).

- [ ] **Step 8: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At \
 -c "select count(*), count(distinct ne_ccor), sum(despesas_empenhadas), sum(despesas_liquidadas), sum(despesas_pagas), sum(restos_a_pagar_inscritos_acumulavel), sum(restos_a_pagar_pagos) from mir_convenios.fato_execucao_orcamentaria" \
 -c "select count(*) filter (where sk_emenda <> -1), count(*) filter (where sk_emenda <> -1 and sk_parlamentar = -1) from mir_convenios.fato_execucao_orcamentaria" \
 -c "select 'fluxo', count(*) from mir_convenios.fato_fluxo_financeiro union all select 'crono', count(*) from mir_convenios.fato_cronograma_desembolso union all select 'evento', count(*) from mir_convenios.fato_evento_convenio union all select 'fluxo sem data', count(*) from mir_convenios.fato_fluxo_financeiro where sk_tempo = -1"
```
Expected: `751|254|77251024.63|44951599.26|43954309.26|22848672.28|18519367.24`; `596|47` (47 linhas de emenda de autores sem cadastro, `prioridade_match = 3`, ficam com parlamentar `-1`); `fluxo|22438`, `crono|1177`, `evento|15903`, `fluxo sem data|28`.

- [ ] **Step 9: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/models/mir_convenios/fato_execucao_orcamentaria.sql $M/models/mir_convenios/fato_fluxo_financeiro.sql $M/models/mir_convenios/fato_cronograma_desembolso.sql $M/models/mir_convenios/fato_evento_convenio.sql $M/models/mir_convenios/schema.yml $M/tests/mir_convenios/mir_convenios_reconciliacao.sql"
git add -- $P
git commit -m "feat(dbt/mir): fatos de execucao, fluxo financeiro, cronograma e eventos de convenios" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 7: Posição por convênio (`fato_convenio_posicao`)

**Files:**
- Create: `models/mir_convenios/fato_convenio_posicao.sql`
- Modify: `models/mir_convenios/schema.yml` (acrescentar)
- Test: `tests/mir_convenios/fato_convenio_posicao_consistente.sql`

**Interfaces:**
- Consumes: `fk` (Tarefa 3); `dim_convenio`, `dim_convenente`, `dim_localidade` (Tarefa 5) via `relationships`; as fatos da Tarefa 6 (só no teste); `ref("convenio_mir")`, `ref("convenio_movimento_financeiro")`, `ref("convenio_evento")`, `ref("convenio_contagens")` (inclui `qtd_empenhos_siconv`, `valor_empenhado_siconv` da Tarefa 1), `ref("execucao_ne")`.
- Produces: `mir_convenios.fato_convenio_posicao`, uma linha por convênio (PK `sk_convenio`). A Tarefa 8 compara esta tabela com o gold antigo.

Duas medidas de empenhado, com nomes distintos: `valor_empenhado_siconv` (registro do SICONV, histórico completo, mesma medida do gold antigo) e `despesas_empenhadas`/`liquidadas`/`pagas`/RAP (NEs do núcleo SIAFI, só os exercícios do relatório do Tesouro; **nulas** quando o convênio não tem NE, para não parecer execução zero). Os "dias sem repasse" do gold antigo não entram: o BI calcula a partir de `data_ultimo_desembolso`.

- [ ] **Step 1: Escrever o teste de consistência**

Criar `tests/mir_convenios/fato_convenio_posicao_consistente.sql`:

```sql
-- Falha se a posicao de algum convenio divergir da soma das fatos
-- transacionais do mesmo convenio, ou se faltar/sobrar convenio.
with
    fluxo as (
        select
            sk_convenio,
            sum(valor) filter (where tipo_movimento = 'Desembolso federal') as desembolsado,
            count(*) filter (where tipo_movimento = 'Desembolso federal') as qtd_desembolsos,
            sum(valor) filter (
                where tipo_movimento = 'Pagamento a fornecedor'
            ) as pago_fornecedores,
            sum(valor) filter (where tipo_movimento = 'Pagamento de tributo') as tributos
        from {{ ref("fato_fluxo_financeiro") }}
        group by sk_convenio
    ),

    execucao as (
        select
            sk_convenio,
            sum(despesas_empenhadas) as empenhado,
            sum(despesas_pagas) as pago,
            sum(restos_a_pagar_inscritos_acumulavel) as rap_inscrito
        from {{ ref("fato_execucao_orcamentaria") }}
        group by sk_convenio
    ),

    eventos as (
        select
            sk_convenio,
            count(*) filter (where tipo_evento = 'Termo aditivo') as qtd_aditivos
        from {{ ref("fato_evento_convenio") }}
        group by sk_convenio
    ),

    convenios as (
        select sk_convenio from {{ ref("dim_convenio") }} where sk_convenio <> -1
    )

select coalesce(p.sk_convenio, c.sk_convenio) as sk_convenio
from {{ ref("fato_convenio_posicao") }} as p
full join convenios as c on c.sk_convenio = p.sk_convenio
left join fluxo as f on f.sk_convenio = p.sk_convenio
left join execucao as e on e.sk_convenio = p.sk_convenio
left join eventos as v on v.sk_convenio = p.sk_convenio
where
    p.sk_convenio is null
    or c.sk_convenio is null
    or p.valor_desembolsado <> coalesce(f.desembolsado, 0)
    or p.qtd_desembolsos <> coalesce(f.qtd_desembolsos, 0)
    or p.valor_pago_fornecedores <> coalesce(f.pago_fornecedores, 0)
    or p.valor_tributos <> coalesce(f.tributos, 0)
    or coalesce(p.despesas_empenhadas, 0) <> coalesce(e.empenhado, 0)
    or coalesce(p.despesas_pagas, 0) <> coalesce(e.pago, 0)
    or coalesce(p.restos_a_pagar_inscritos_acumulavel, 0) <> coalesce(e.rap_inscrito, 0)
    or p.qtd_aditivos <> coalesce(v.qtd_aditivos, 0)
```

- [ ] **Step 2: Criar `models/mir_convenios/fato_convenio_posicao.sql`**

```sql
-- Posicao acumulada de cada convenio do MIR (snapshot), uma linha por
-- convenio. Os valores pactuados vem do SICONV; movimentos, eventos e
-- contagens, da silver; a execucao orcamentaria, do nucleo SIAFI.
-- Empenhado aparece de duas fontes: o registro do SICONV (historico completo,
-- mesma medida do gold antigo) e as NEs do relatorio do Tesouro (so os
-- exercicios cobertos, com liquidado, pago e RAP; nulas sem NE).
with
    movimentos as (
        select
            nr_convenio,
            sum(valor) filter (
                where tipo_movimento = 'Desembolso federal'
            ) as valor_desembolsado,
            count(*) filter (where tipo_movimento = 'Desembolso federal') as qtd_desembolsos,
            sum(valor) filter (
                where tipo_movimento = 'Contrapartida depositada'
            ) as valor_contrapartida_depositada,
            sum(valor) filter (where tipo_movimento = 'Desbloqueio') as valor_desbloqueado,
            sum(valor_bloqueado) filter (
                where tipo_movimento = 'Desbloqueio'
            ) as valor_bloqueado,
            sum(valor) filter (
                where tipo_movimento = 'Pagamento a fornecedor'
            ) as valor_pago_fornecedores,
            count(*) filter (where tipo_movimento = 'Pagamento a fornecedor') as qtd_pagamentos,
            max(data_movimento) filter (
                where tipo_movimento = 'Pagamento a fornecedor'
            ) as data_ultimo_pagamento,
            sum(valor) filter (where tipo_movimento = 'Pagamento de tributo') as valor_tributos,
            count(*) filter (
                where tipo_movimento = 'Pagamento de tributo'
            ) as qtd_pagamentos_tributo
        from {{ ref("convenio_movimento_financeiro") }}
        group by nr_convenio
    ),

    eventos as (
        select
            nr_convenio,
            count(*) filter (where tipo_evento = 'Termo aditivo') as qtd_aditivos,
            count(*) filter (where tipo_evento = 'Prorrogação de ofício') as qtd_prorrogacoes
        from {{ ref("convenio_evento") }}
        group by nr_convenio
    ),

    -- RAP inscrito sem as reinscricoes: o saldo nao pago reaparece como
    -- inscrito no exercicio seguinte e nao pode ser somado de novo
    execucao as (
        select
            nr_instrumento as nr_convenio,
            sum(despesas_empenhadas) as despesas_empenhadas,
            sum(despesas_liquidadas) as despesas_liquidadas,
            sum(despesas_pagas) as despesas_pagas,
            sum(
                case when reinscricao_rap then 0 else restos_a_pagar_inscritos end
            ) as restos_a_pagar_inscritos_acumulavel,
            sum(restos_a_pagar_pagos) as restos_a_pagar_pagos
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV'
        group by nr_instrumento
    )

select
    {{ fk(["c.nr_convenio"]) }} as sk_convenio,
    {{ fk(["c.convenente_documento"]) }} as sk_convenente,
    {{ fk(["coalesce(c.cod_municipio_ibge, 'UF-' || c.uf)"]) }} as sk_localidade,

    -- Pactuado
    c.valor_global_original as valor_firmado_inicial,
    c.valor_global as valor_firmado_atualizado,
    c.valor_repasse as valor_repasse_previsto,
    c.valor_contrapartida as valor_contrapartida_prevista,
    c.valor_saldo_conta,

    -- Movimentos financeiros
    coalesce(m.valor_desembolsado, 0) as valor_desembolsado,
    coalesce(m.qtd_desembolsos, 0) as qtd_desembolsos,
    k.data_ultimo_desembolso,
    coalesce(m.valor_contrapartida_depositada, 0) as valor_contrapartida_depositada,
    coalesce(m.valor_desbloqueado, 0) as valor_desbloqueado,
    coalesce(m.valor_bloqueado, 0) as valor_bloqueado,
    coalesce(m.valor_pago_fornecedores, 0) as valor_pago_fornecedores,
    coalesce(m.qtd_pagamentos, 0) as qtd_pagamentos,
    m.data_ultimo_pagamento,
    coalesce(m.valor_tributos, 0) as valor_tributos,
    coalesce(m.qtd_pagamentos_tributo, 0) as qtd_pagamentos_tributo,

    -- Empenhado registrado no SICONV (historico completo)
    k.valor_empenhado_siconv,
    k.qtd_empenhos_siconv,

    -- Execucao SIAFI (NEs do relatorio do Tesouro; nulo sem NE)
    x.despesas_empenhadas,
    x.despesas_liquidadas,
    x.despesas_pagas,
    x.restos_a_pagar_inscritos_acumulavel,
    x.restos_a_pagar_pagos,

    -- Contagens
    k.qtd_metas,
    k.qtd_licitacoes,
    k.valor_licitado,
    coalesce(e.qtd_aditivos, 0) as qtd_aditivos,
    coalesce(e.qtd_prorrogacoes, 0) as qtd_prorrogacoes
from {{ ref("convenio_mir") }} as c
left join movimentos as m on m.nr_convenio = c.nr_convenio
left join eventos as e on e.nr_convenio = c.nr_convenio
left join execucao as x on x.nr_convenio = c.nr_convenio
left join {{ ref("convenio_contagens") }} as k on k.nr_convenio = c.nr_convenio
```

- [ ] **Step 3: Documentar em `models/mir_convenios/schema.yml` (acrescentar em `models:`)**

```yaml
  - name: fato_convenio_posicao
    description: >
      Posicao acumulada por convenio (snapshot), uma linha por convenio.
      valor_empenhado_siconv e o empenhado registrado no SICONV (historico
      completo); despesas_* e restos_a_pagar_* vem das NEs do relatorio do
      Tesouro e sao nulos quando o convenio nao tem NE nesse periodo.
    columns:
      - name: sk_convenio
        tests:
          - unique
          - not_null
          - relationships: {to: ref('dim_convenio'), field: sk_convenio}
      - name: sk_convenente
        tests:
          - not_null
          - relationships: {to: ref('dim_convenente'), field: sk_convenente}
      - name: sk_localidade
        tests:
          - not_null
          - relationships: {to: ref('dim_localidade'), field: sk_localidade}
      - name: restos_a_pagar_inscritos_acumulavel
        description: "RAP inscrito sem as reinscricoes (somavel entre exercicios)."
```

- [ ] **Step 4: Formatar, construir e testar**

Run (da raiz do repo): sqlfmt no modelo e no teste.
Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s fato_convenio_posicao`
Expected: `ERROR=0` e `WARN=0` (o teste de consistência também lê as fatos da Tarefa 6, já construídas).

- [ ] **Step 5: Conferir contra a linha de base**

Run:
```bash
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "select count(*), sum(valor_firmado_atualizado), sum(valor_desembolsado), sum(valor_pago_fornecedores), sum(valor_empenhado_siconv), sum(qtd_empenhos_siconv), count(despesas_empenhadas), sum(despesas_empenhadas), sum(restos_a_pagar_inscritos_acumulavel), sum(qtd_aditivos), sum(qtd_pagamentos) from mir_convenios.fato_convenio_posicao"
```
Expected: `643|179299949.38|128160017.70|100329484.72|143870442.64|905|225|77251024.63|22848672.28|468|20911`.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
M=airflow_lappis/dags/dbt/mir
P="$M/models/mir_convenios/fato_convenio_posicao.sql $M/models/mir_convenios/schema.yml $M/tests/mir_convenios/fato_convenio_posicao_consistente.sql"
git add -- $P
git commit -m "feat(dbt/mir): posicao acumulada por convenio em mir_convenios" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

---

### Task 8: Paridade com o gold antigo e verificação final

**Files:**
- Create: `analyses/paridade_mir_convenios.sql` (temporário: apagar na etapa 5, junto com o gold antigo)

**Interfaces:**
- Consumes: `fato_convenio_posicao`, `dim_convenio`, `fato_evento_convenio` (Tarefas 5–7); `ref("resumo_convenios")`, `ref("resumo_termos_fomento")` (gold antigo, só leitura).
- Produces: uma linha por convênio × medida que diverge (`tabela`, `nr_convenio`, `medida`, `valor_antigo`, `valor_novo`). Uma análise do dbt só é compilada, nunca materializada, então não entra na DAG.

A análise foi validada em 2026-09-29 contra uma emulação do gold montada a partir da silver.

- [ ] **Step 1: Criar `analyses/paridade_mir_convenios.sql`**

```sql
-- Paridade temporaria (spec §11): posicao nova x gold antigo, convenio a
-- convenio e medida a medida. Apagar na etapa 5, junto com o gold antigo.
-- O gold antigo tem linhas repetidas (resumo_convenios: 834 linhas para 643
-- convenios; a repeticao so muda a UG responsavel): fica uma linha por
-- convenio, a que tem UG. As duas tabelas antigas tem as mesmas colunas em
-- ordens diferentes, por isso a lista explicita.
{% set colunas = [
    "nr_convenio", "modalidade_instrumento", "situacao_atual", "origem",
    "valor_firmado_atualizado", "valor_firmado_inicial", "valor_repasse_previsto",
    "saldo_disponivel", "valor_contrapartida_previsto", "valor_total_repassado",
    "quantidade_desembolsos", "data_ultimo_desembolso", "valor_empenhado",
    "quantidade_empenhos", "valor_total_pago", "quantidade_pagamentos",
    "data_ultimo_pagamento", "valor_total_tributos", "quantidade_pagamentos_tributo",
    "valor_contrapartida_depositado", "valor_desbloqueado", "valor_bloqueado",
    "quantidade_licitacoes", "valor_total_contratado", "quantidade_metas",
    "quantidade_aditivos", "quantidade_prorrogacoes", "quantidade_mudancas_situacao",
    "inadimplente", "rescindido", "anulado", "prazo_vigente", "prazo_meta_expirado",
] %}
with
    antigo as (
        select 'resumo_convenios' as tabela, {{ colunas | join(", ") }}
        from
            (
                select distinct on (nr_convenio) *
                from {{ ref("resumo_convenios") }}
                order by nr_convenio, ug_responsavel_codigo nulls last
            ) as r

        union all

        select 'resumo_termos_fomento' as tabela, {{ colunas | join(", ") }}
        from
            (
                select distinct on (nr_convenio) *
                from {{ ref("resumo_termos_fomento") }}
                order by nr_convenio, ug_responsavel_codigo nulls last
            ) as t
    ),

    situacoes as (
        select sk_convenio, count(*) as qtd_mudancas_situacao
        from {{ ref("fato_evento_convenio") }}
        where tipo_evento = 'Mudança de situação'
        group by sk_convenio
    ),

    novo as (
        select
            d.nr_convenio,
            d.modalidade,
            d.situacao,
            d.origem_recurso,
            d.inadimplente,
            d.rescindido,
            d.anulado,
            d.vigente,
            d.meta_expirada,
            coalesce(s.qtd_mudancas_situacao, 0) as qtd_mudancas_situacao,
            p.*
        from {{ ref("fato_convenio_posicao") }} as p
        inner join {{ ref("dim_convenio") }} as d on d.sk_convenio = p.sk_convenio
        left join situacoes as s on s.sk_convenio = p.sk_convenio
    ),

    -- Cada tabela antiga e comparada so com os convenios que ela cobre; o
    -- resumo de termos de fomento cobre so a modalidade TERMO DE FOMENTO
    pares as (
        select a.tabela, a.nr_convenio as nr_antigo, n.nr_convenio as nr_novo, a, n
        from antigo as a
        full join
            (
                select n.*, t.tabela
                from novo as n
                cross join
                    (
                        values ('resumo_convenios'), ('resumo_termos_fomento')
                    ) as t(tabela)
                where
                    t.tabela = 'resumo_convenios' or n.modalidade = 'TERMO DE FOMENTO'
            ) as n
            on n.nr_convenio = a.nr_convenio
            and n.tabela = a.tabela
    )

select
    coalesce(p.tabela, (p.n).tabela) as tabela,
    coalesce(p.nr_antigo, p.nr_novo) as nr_convenio,
    c.medida,
    c.valor_antigo,
    c.valor_novo
from pares as p
cross join lateral (
    values
        (
            'presenca',
            (p.nr_antigo is not null)::text,
            (p.nr_novo is not null)::text,
            p.nr_antigo is null or p.nr_novo is null
        ),
        (
            'modalidade',
            (p.a).modalidade_instrumento,
            (p.n).modalidade,
            (p.a).modalidade_instrumento is distinct from (p.n).modalidade
        ),
        (
            'situacao',
            (p.a).situacao_atual,
            (p.n).situacao,
            (p.a).situacao_atual is distinct from (p.n).situacao
        ),
        (
            'origem',
            (p.a).origem,
            (p.n).origem_recurso,
            case
                when (p.a).origem like 'Emenda%' then 'Emenda' else 'Recurso próprio'
            end
            is distinct from (p.n).origem_recurso
        ),
        (
            'valor_firmado_atualizado',
            (p.a).valor_firmado_atualizado::text,
            (p.n).valor_firmado_atualizado::text,
            coalesce((p.a).valor_firmado_atualizado, 0)
            <> coalesce((p.n).valor_firmado_atualizado, 0)
        ),
        (
            'valor_firmado_inicial',
            (p.a).valor_firmado_inicial::text,
            (p.n).valor_firmado_inicial::text,
            coalesce((p.a).valor_firmado_inicial, 0)
            <> coalesce((p.n).valor_firmado_inicial, 0)
        ),
        (
            'valor_repasse_previsto',
            (p.a).valor_repasse_previsto::text,
            (p.n).valor_repasse_previsto::text,
            coalesce((p.a).valor_repasse_previsto, 0)
            <> coalesce((p.n).valor_repasse_previsto, 0)
        ),
        (
            'saldo_em_conta',
            (p.a).saldo_disponivel::text,
            (p.n).valor_saldo_conta::text,
            coalesce((p.a).saldo_disponivel, 0) <> coalesce((p.n).valor_saldo_conta, 0)
        ),
        (
            'contrapartida_prevista',
            (p.a).valor_contrapartida_previsto::text,
            (p.n).valor_contrapartida_prevista::text,
            coalesce((p.a).valor_contrapartida_previsto, 0)
            <> coalesce((p.n).valor_contrapartida_prevista, 0)
        ),
        (
            'desembolsado',
            (p.a).valor_total_repassado::text,
            (p.n).valor_desembolsado::text,
            coalesce((p.a).valor_total_repassado, 0)
            <> coalesce((p.n).valor_desembolsado, 0)
        ),
        (
            'qtd_desembolsos',
            (p.a).quantidade_desembolsos::text,
            (p.n).qtd_desembolsos::text,
            coalesce((p.a).quantidade_desembolsos, 0) <> coalesce((p.n).qtd_desembolsos, 0)
        ),
        (
            'data_ultimo_desembolso',
            (p.a).data_ultimo_desembolso::text,
            (p.n).data_ultimo_desembolso::text,
            (p.a).data_ultimo_desembolso is distinct from (p.n).data_ultimo_desembolso
        ),
        (
            'empenhado_siconv',
            (p.a).valor_empenhado::text,
            (p.n).valor_empenhado_siconv::text,
            coalesce((p.a).valor_empenhado, 0) <> coalesce((p.n).valor_empenhado_siconv, 0)
        ),
        (
            'qtd_empenhos_siconv',
            (p.a).quantidade_empenhos::text,
            (p.n).qtd_empenhos_siconv::text,
            coalesce((p.a).quantidade_empenhos, 0) <> coalesce((p.n).qtd_empenhos_siconv, 0)
        ),
        (
            'pago_fornecedores',
            (p.a).valor_total_pago::text,
            (p.n).valor_pago_fornecedores::text,
            coalesce((p.a).valor_total_pago, 0) <> coalesce((p.n).valor_pago_fornecedores, 0)
        ),
        (
            'qtd_pagamentos',
            (p.a).quantidade_pagamentos::text,
            (p.n).qtd_pagamentos::text,
            coalesce((p.a).quantidade_pagamentos, 0) <> coalesce((p.n).qtd_pagamentos, 0)
        ),
        (
            'data_ultimo_pagamento',
            (p.a).data_ultimo_pagamento::text,
            (p.n).data_ultimo_pagamento::text,
            (p.a).data_ultimo_pagamento is distinct from (p.n).data_ultimo_pagamento
        ),
        (
            'tributos',
            (p.a).valor_total_tributos::text,
            (p.n).valor_tributos::text,
            coalesce((p.a).valor_total_tributos, 0) <> coalesce((p.n).valor_tributos, 0)
        ),
        (
            'qtd_pagamentos_tributo',
            (p.a).quantidade_pagamentos_tributo::text,
            (p.n).qtd_pagamentos_tributo::text,
            coalesce((p.a).quantidade_pagamentos_tributo, 0)
            <> coalesce((p.n).qtd_pagamentos_tributo, 0)
        ),
        (
            'contrapartida_depositada',
            (p.a).valor_contrapartida_depositado::text,
            (p.n).valor_contrapartida_depositada::text,
            coalesce((p.a).valor_contrapartida_depositado, 0)
            <> coalesce((p.n).valor_contrapartida_depositada, 0)
        ),
        (
            'desbloqueado',
            (p.a).valor_desbloqueado::text,
            (p.n).valor_desbloqueado::text,
            coalesce((p.a).valor_desbloqueado, 0) <> coalesce((p.n).valor_desbloqueado, 0)
        ),
        (
            'bloqueado',
            (p.a).valor_bloqueado::text,
            (p.n).valor_bloqueado::text,
            coalesce((p.a).valor_bloqueado, 0) <> coalesce((p.n).valor_bloqueado, 0)
        ),
        (
            'qtd_licitacoes',
            (p.a).quantidade_licitacoes::text,
            (p.n).qtd_licitacoes::text,
            coalesce((p.a).quantidade_licitacoes, 0) <> coalesce((p.n).qtd_licitacoes, 0)
        ),
        (
            'valor_licitado',
            (p.a).valor_total_contratado::text,
            (p.n).valor_licitado::text,
            coalesce((p.a).valor_total_contratado, 0) <> coalesce((p.n).valor_licitado, 0)
        ),
        (
            'qtd_metas',
            (p.a).quantidade_metas::text,
            (p.n).qtd_metas::text,
            coalesce((p.a).quantidade_metas, 0) <> coalesce((p.n).qtd_metas, 0)
        ),
        (
            'qtd_aditivos',
            (p.a).quantidade_aditivos::text,
            (p.n).qtd_aditivos::text,
            coalesce((p.a).quantidade_aditivos, 0) <> coalesce((p.n).qtd_aditivos, 0)
        ),
        (
            'qtd_prorrogacoes',
            (p.a).quantidade_prorrogacoes::text,
            (p.n).qtd_prorrogacoes::text,
            coalesce((p.a).quantidade_prorrogacoes, 0) <> coalesce((p.n).qtd_prorrogacoes, 0)
        ),
        (
            'qtd_mudancas_situacao',
            (p.a).quantidade_mudancas_situacao::text,
            (p.n).qtd_mudancas_situacao::text,
            coalesce((p.a).quantidade_mudancas_situacao, 0)
            <> coalesce((p.n).qtd_mudancas_situacao, 0)
        ),
        (
            'inadimplente',
            (p.a).inadimplente::text,
            (p.n).inadimplente::text,
            coalesce((p.a).inadimplente, false) <> coalesce((p.n).inadimplente, false)
        ),
        (
            'rescindido',
            (p.a).rescindido::text,
            (p.n).rescindido::text,
            coalesce((p.a).rescindido, false) <> coalesce((p.n).rescindido, false)
        ),
        (
            'anulado',
            (p.a).anulado::text,
            (p.n).anulado::text,
            coalesce((p.a).anulado, false) <> coalesce((p.n).anulado, false)
        ),
        (
            'vigente',
            (p.a).prazo_vigente::text,
            (p.n).vigente::text,
            coalesce((p.a).prazo_vigente, false) <> coalesce((p.n).vigente, false)
        ),
        (
            'meta_expirada',
            (p.a).prazo_meta_expirado::text,
            (p.n).meta_expirada::text,
            coalesce((p.a).prazo_meta_expirado, false)
            <> coalesce((p.n).meta_expirada, false)
        )
) as c(medida, valor_antigo, valor_novo, difere)
where c.difere
```

- [ ] **Step 2: Compilar e rodar**

Run:
```bash
poetry run dbt compile --profiles-dir . --no-partial-parse -s paridade_mir_convenios
Q=$(cat target/compiled/mir/analyses/paridade_mir_convenios.sql)
docker exec mir-dump-pg17 psql -U postgres -d analytics -At -c "select tabela, medida, count(*) from ($Q) as x group by 1, 2 order by 1, 2"
```

Expected (todas as diferenças são aceitas; qualquer outra medida é regressão e bloqueia a etapa):

| Tabela | Medida | Convênios | Classificação |
|---|---|---|---|
| `resumo_convenios` | `qtd_mudancas_situacao` | 520 | bug antigo corrigido: o gold antigo contava as linhas repetidas de `historico_situacao` |
| `resumo_convenios` | `origem` | 431 | decisão do usuário: 13 passam de Recurso próprio para Emenda (vínculo NE novo) e 418 passam para Não identificada (sem NE no relatório do Tesouro) |
| `resumo_convenios` | `vigente`, `meta_expirada` | 1 cada | efeito da data: o gold antigo foi gerado antes de 27/09/2026, fim da vigência e da meta do convênio 963677. O número depende do dia em que a análise roda |
| `resumo_termos_fomento` | `qtd_mudancas_situacao` | 196 | idem |
| `resumo_termos_fomento` | `origem` | 46 | idem |
| `resumo_termos_fomento` | `vigente`, `meta_expirada` | 1 cada | idem (963677 é termo de fomento) |

Nenhuma linha com `medida = 'presenca'`: os 643 convênios (e os 234 termos de fomento) estão nos dois lados. Os valores somados do gold antigo sem repetição batem com o novo em todas as outras medidas.

Se aparecer medida fora da tabela, listar os convênios com `select * from ($Q) as x where medida = '<medida>' limit 20`, classificar como bug antigo corrigido ou regressão e parar para relatar antes do commit.

- [ ] **Step 3: Construir o mart e a silver inteiros**

Run: `poetry run dbt build --profiles-dir . --no-partial-parse -s path:models/mir_silver path:models/mir_convenios uf_regiao`
Expected: `ERROR=0`; `WARN=1` (só o aviso de complemento próprio da silver, linha de base 2).

- [ ] **Step 4: Confirmar que nenhum modelo antigo mudou nesta etapa**

Run (da raiz): `git diff 9cb6fcc --stat -- airflow_lappis/dags/dbt/mir/models ':!airflow_lappis/dags/dbt/mir/models/mir_silver' ':!airflow_lappis/dags/dbt/mir/models/mir_convenios'`
Expected: saída vazia.

- [ ] **Step 5: Lint**

Run (da raiz): sqlfmt `--check` em `airflow_lappis/dags/dbt/mir/models/mir_silver airflow_lappis/dags/dbt/mir/models/mir_convenios airflow_lappis/dags/dbt/mir/tests/mir_silver airflow_lappis/dags/dbt/mir/tests/mir_convenios airflow_lappis/dags/dbt/mir/macros/mir_gold airflow_lappis/dags/dbt/mir/analyses`
Expected: todos passam.

- [ ] **Step 6: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P=airflow_lappis/dags/dbt/mir/analyses/paridade_mir_convenios.sql
git add -- $P
git commit -m "test(dbt/mir): paridade temporaria de mir_convenios com o gold antigo" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- $P
```

## Fora desta etapa

- Etapa 3: mart `mir_teds` (reusa as macros de `macros/mir_gold/`; a cascata de `num_transf` migra para `mir_silver`).
- Etapa 4: mart `mir_emendas`, com `dim_instrumento_executor` (inclui o tipo "Convênio de outro órgão" para os 24 convênios fora de `convenio_mir`) e o teste de consistência entre marts.
- Etapa 5: migração do I1, remoção do gold antigo e desta análise de paridade. Os painéis que somam `resumo_convenios` hoje contam em dobro os 190 convênios repetidos (32% a 52% a mais); os totais do painel novo serão menores, e o usuário vai avisar a equipe.
- A regra de origem do recurso pelo resultado primário (RP 2 próprio, RP 6 emenda) continua adiada pelo usuário.
