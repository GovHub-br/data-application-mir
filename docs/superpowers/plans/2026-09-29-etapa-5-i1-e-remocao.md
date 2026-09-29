# Etapa 5: Migração do I1 e remoção do legado — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o indicador I1 ler os marts `mir_teds` e `mir_convenios`, remover do dbt os 41 modelos antigos de silver/gold substituídos pelos marts e entregar à equipe o script de `drop` das tabelas órfãs e o guia de migração dos painéis do Power BI.

**Architecture:** O plugin do I1 continua com funções puras. Ele passa a receber as tabelas dos marts (dimensões e posições) e junta as chaves `sk_*` em Python; as agregações e as saídas não mudam, exceto a coluna `n_linhas_resumo`, que vira `qtd_nes`. Os modelos antigos saem do dbt, mas as tabelas continuam no banco, paradas, até a equipe migrar os painéis e rodar o script de `drop` manualmente (decisão do usuário em 2026-09-29).

**Tech Stack:** Python 3.11 e pytest (Airflow plugins), dbt-core/dbt-postgres 1.7.13, PostgreSQL 17 (container `mir-dump-pg17`, porta 5433, database `analytics`), shandy-sqlfmt 0.32.0.

**Spec:** `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§1, §9, §10, §12, §13).

## Global Constraints

- A lógica de cálculo do I1 não muda: universo, cortes, agregações e nomes das seis saídas ficam iguais. Muda só a origem dos dados. Na saída `i1_ted_por_instrumento`, a coluna `n_linhas_resumo` é trocada por `qtd_nes` (decisão do usuário em 2026-09-29).
- O ajuste dos testes do I1 se limita ao formato das entradas. Os testes de regressão contra os CSVs do BI (`tests/fixtures/indicadores/i1/*.csv`) não mudam, e os CSVs também não.
- Valores do I1 podem mudar onde o modelo novo cobre cenários que o antigo perdia (decisão do usuário em 2026-09-29). Toda diferença é listada com a causa na seção "Resultado da paridade do I1" deste plano, que alimenta o PR.
- Saem do dbt 41 modelos: `siconv_dbt/silver/*` (25), `siconv_dbt/gold/*` (2), `empenhos_ted_dbt/silver/*` (5), `empenhos_ted_dbt/views/*` (1), `empenhos_ted_dbt/gold/*` (2), `emendas_dbt/gold/*` (3) e 3 de `emendas_dbt/silver/` (`emendas_orcamento_execucao`, `emendas_partidos`, `instrumentos_emendas`).
- **`emendas_dbt/silver/planos_partidos` fica.** São os planos de ação das transferências especiais (emendas PIX), fora do escopo da remodelagem (spec §1), e nenhum mart os substitui.
- A bronze, `dados_abertos_dbt/silver/parlamentares_historico`, `contratos_dbt` e `ppa_dbt` não mudam. `dbt_project.yml` não muda: os blocos `siconv_dbt`, `empenhos_ted_dbt` e `emendas_dbt` continuam configurando a bronze e o `planos_partidos`.
- Nenhuma tabela é apagada por este plano. O script de `drop` é entregue para o usuário rodar em produção. No banco local, o script é só simulado: roda dentro de uma transação que termina em `rollback` (decisão do usuário em 2026-09-29: "Só simular").
- Todo `.sql` alterado passa pelo sqlfmt antes do commit.
- Commits só com os arquivos da tarefa (`git add -- <paths>` e `git commit ... -- <paths>`). Há ~90 arquivos de `dicionario-mir/` em stage que não podem ser commitados, retirados do stage nem resetados. Mensagem: assunto e, num segundo `-m`, só `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Nunca rodar `dbt build/run` sem `-s`, nunca usar operadores `+`, nunca `--full-refresh`.

### Ambiente local

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
export DB_DW_HOST_MIR=localhost DB_DW_PORT_MIR=5433 DB_DW_USER_MIR=postgres \
       DB_DW_PASSWORD_MIR=postgres DB_DW_DBNAME_MIR=analytics DB_DW_SCHEMA_MIR=mir
```

- dbt: `dbt <cmd> --profiles-dir . --no-partial-parse ...`.
- pytest, da raiz do repositório: `python3 -m pytest tests/test_plugins/test_indicadores_i1.py -q -p no:cacheprovider` (o `pyproject.toml` já põe `airflow_lappis/plugins` no `pythonpath`).
- sqlfmt, da raiz do repositório: `/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad/sqlfmt-venv/bin/sqlfmt <arquivos>`.
- Consultas: `PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -At -c "<sql>"`.
- Se o banco não responder (o WSL pode ter reiniciado): `docker start mir-dump-pg17`.

### Linha de base medida em 2026-09-29 (dump local)

| Objeto | Valor |
|---|---|
| Suíte do I1 | 27 testes passando |
| `mir_teds.dim_plano_acao` | 120 planos (sem o `-1`), um por linha em `fato_plano_acao_posicao`; `empenhado_bruto − empenho_anulado = despesas_empenhadas` em todos |
| Campos do plano (novo × `siafi_dbt.planos_acao_ted`) | ano, `num_transf` = `sq_instrumento`, valor firmado, situação e executor iguais nos 120 |
| Planos com NE em mais de um programa | 5 de 49 |
| `mir_convenios.dim_convenio` | 643 convênios (sem o `-1`), um por linha em `fato_convenio_posicao` |
| Convênios de 2023 em diante (novo × `resumo_convenios` deduplicado) | 225; empenhado SICONV, pago, firmado, UF/município, convenente e situação iguais nos 225; origem difere em 23 (Emenda no novo, sem parlamentar no antigo: 15 termos de fomento, R$ 2.972.211,51; 8 convênios, R$ 2.458.200,00) |
| Objetos antigos no banco | 41 tabelas e 1 view (42 modelos, contando `planos_partidos`); nenhum objeto do banco local depende deles |

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `airflow_lappis/plugins/indicadores/i1_valor_executado.py` | Modificar | Funções do I1 lendo as tabelas dos marts |
| `tests/test_plugins/test_indicadores_i1.py` | Modificar | Entradas no formato dos marts |
| `airflow_lappis/dags/indicadores/mir/i1_valor_executado_dag.py` | Modificar | `FONTES` apontando para os marts |
| `airflow_lappis/dags/dbt/mir/models/{siconv_dbt,empenhos_ted_dbt,emendas_dbt}/...` | Remover | 41 modelos antigos e seus `schema.yml` |
| `airflow_lappis/dags/dbt/mir/models/emendas_dbt/silver/schema.yml` | Modificar | Fica só o bloco do `planos_partidos` |
| `airflow_lappis/dags/dbt/mir/analyses/paridade_mir_*.sql` | Remover | Análises temporárias de paridade |
| `airflow_lappis/dags/dbt/mir/tests/test_ted_resumo_orcamentario_*.sql`, `tests/test_num_transf_n_plano_acao_cardinalidade.sql` | Remover | Testes dos modelos antigos |
| comentários em `macros/star_except.sql`, `macros/mir_silver/parlamentar_na_data.sql`, `models/mir_silver/{convenio_mir,vinculo_ne_convenio,ted_ne_transferencia}.sql`, `models/mir_silver/schema.yml` | Modificar | Não citar modelo removido como se existisse |
| `.claude/skills/govhub-pipeline-guide/SKILL.md` | Modificar | Exemplo de silver apontava para modelo removido |
| `docs/mir-drop-legado.sql` | Criar | Script de `drop` explícito para o usuário rodar em produção |
| `docs/mir-guia-migracao-power-bi.md` | Criar | Tabela antiga → tabelas novas, para a equipe dos painéis |
| `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` | Modificar | §9, §10, §12 e §13 com o que foi feito |

---

### Task 1: Plugin do I1 lê os marts

**Files:**
- Modify: `airflow_lappis/plugins/indicadores/i1_valor_executado.py`
- Test: `tests/test_plugins/test_indicadores_i1.py`

**Interfaces:**
- Produces (usadas pela Tarefa 2):
  - `classificar_etapa_cadeia(planos: list[dict], posicao_planos: list[dict]) -> dict[str, str]`
  - `calcular_teds(planos, posicao_planos, execucao_teds, acoes_teds, etapa_por_plano: dict[str, str] | None = None) -> list[dict]`
  - `calcular_convenios(convenios, posicao_convenios, convenentes, localidades, ano_corte: int = ANO_CORTE) -> list[dict]`
  - `calcular_i1(planos, posicao_planos, execucao_teds, acoes_teds, convenios, posicao_convenios, convenentes, localidades) -> dict[str, list[dict]]`
  - Entradas = linhas (dicts) de: `planos` = `mir_teds.dim_plano_acao`; `posicao_planos` = `mir_teds.fato_plano_acao_posicao`; `execucao_teds` = `mir_teds.fato_execucao_orcamentaria`; `acoes_teds` = `mir_teds.dim_acao_orcamentaria`; `convenios` = `mir_convenios.dim_convenio`; `posicao_convenios` = `mir_convenios.fato_convenio_posicao`; `convenentes` = `mir_convenios.dim_convenente`; `localidades` = `mir_convenios.dim_localidade`.
  - `agregar_teds_por_executor`, `agregar_convenios_por_uf`, `agregar_convenios_por_municipio` e `calcular_carteira` não mudam.

- [ ] **Step 1: Reescrever os testes no formato dos marts**

Substituir o conteúdo de `tests/test_plugins/test_indicadores_i1.py` por:

```python
"""Testes do indicador I1 — Valor Executado por Instrumento.

Cada teste unitário cobre uma decisão metodológica registrada no script
original da equipe de BI (i1_valor_executado.py / i1_etapa_cadeia_ted.R).
As entradas têm o formato das tabelas dos marts mir_teds e mir_convenios.
Os testes de regressão usam os CSVs entregues pelo BI em `tests/fixtures`
como saída esperada das agregações.
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from indicadores.i1_valor_executado import (
    agregar_convenios_por_municipio,
    agregar_convenios_por_uf,
    agregar_teds_por_executor,
    calcular_carteira,
    calcular_convenios,
    calcular_i1,
    calcular_teds,
    classificar_etapa_cadeia,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i1"


# ---------------------------------------------------------------------------
# Helpers — linhas no formato das tabelas dos marts
# ---------------------------------------------------------------------------
def _plano(id_plano_acao, situacao="APROVADO", sq="900", **extra):
    """Linha de mir_teds.dim_plano_acao (sk = id, para simplificar)."""
    base = {
        "sk_plano_acao": id_plano_acao,
        "id_plano_acao": id_plano_acao,
        "num_transf": sq,
        "situacao": situacao,
        "ano": 2024,
        "sigla_unidade_descentralizada": "UFX",
        "unidade_descentralizada": "Universidade X",
        "origem_recurso": "Recurso próprio",
        "execucao_direta": False,
        "execucao_particulares": False,
        "execucao_descentralizada": False,
    }
    base.update(extra)
    return base


def _posicao(sk_plano_acao, firmado=Decimal("1000.00"), bruto=0, anulado=0,
             liquidado=0, pago=0, rap_pago=0, qtd_pf=0, qtd_nc=0, qtd_nes=0):
    """Linha de mir_teds.fato_plano_acao_posicao."""
    return {
        "sk_plano_acao": sk_plano_acao,
        "valor_firmado": firmado,
        "empenhado_bruto": bruto,
        "empenho_anulado": anulado,
        "despesas_liquidadas": liquidado,
        "despesas_pagas": pago,
        "restos_a_pagar_pagos": rap_pago,
        "qtd_pf": qtd_pf,
        "qtd_nc": qtd_nc,
        "qtd_nes": qtd_nes,
    }


def _ne(sk_plano_acao, sk_acao_orcamentaria, empenhado):
    """Linha de mir_teds.fato_execucao_orcamentaria (só as colunas usadas)."""
    return {
        "sk_plano_acao": sk_plano_acao,
        "sk_acao_orcamentaria": sk_acao_orcamentaria,
        "despesas_empenhadas": empenhado,
    }


def _acao(sk_acao_orcamentaria, codigo_programa):
    """Linha de mir_teds.dim_acao_orcamentaria (só as colunas usadas)."""
    return {
        "sk_acao_orcamentaria": sk_acao_orcamentaria,
        "codigo_programa": codigo_programa,
    }


def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              origem="Recurso próprio", empenhado=100, **extra):
    """Um convênio com os campos de dim_convenio, posição, convenente e localidade."""
    base = {
        "nr_convenio": nr,
        "modalidade": "CONVENIO",
        "origem_recurso": origem,
        "situacao": situacao,
        "data_assinatura": assinatura,
        "data_inicio_vigencia": vigencia,
        "uf": "DF",
        "municipio": "BRASÍLIA",
        "convenente_nome": "Prefeitura",
        "convenente_natureza_juridica": "Administração Pública Municipal",
        "valor_firmado_atualizado": 200,
        "valor_empenhado_siconv": empenhado,
        "valor_pago_fornecedores": 50,
    }
    base.update(extra)
    return base


def _fontes_convenios(especificacoes):
    """Separa os convênios nas quatro tabelas de mir_convenios, ligadas por sk."""
    fontes = {
        "convenios": [], "posicao_convenios": [], "convenentes": [], "localidades": [],
    }
    for i, c in enumerate(especificacoes, start=1):
        fontes["convenios"].append({
            "sk_convenio": i,
            "nr_convenio": c["nr_convenio"],
            "modalidade": c["modalidade"],
            "origem_recurso": c["origem_recurso"],
            "situacao": c["situacao"],
            "data_assinatura": c["data_assinatura"],
            "data_inicio_vigencia": c["data_inicio_vigencia"],
        })
        fontes["posicao_convenios"].append({
            "sk_convenio": i,
            "sk_convenente": 100 + i,
            "sk_localidade": 200 + i,
            "valor_firmado_atualizado": c["valor_firmado_atualizado"],
            "valor_empenhado_siconv": c["valor_empenhado_siconv"],
            "valor_pago_fornecedores": c["valor_pago_fornecedores"],
        })
        fontes["convenentes"].append({
            "sk_convenente": 100 + i,
            "convenente_nome": c["convenente_nome"],
            "convenente_natureza_juridica": c["convenente_natureza_juridica"],
        })
        fontes["localidades"].append({
            "sk_localidade": 200 + i,
            "uf": c["uf"],
            "municipio": c["municipio"],
        })
    return fontes


def _ler_fixture(nome, numericos=(), inteiros=()):
    with open(FIXTURES / nome, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f))
    for linha in linhas:
        for col in numericos:
            linha[col] = float(linha[col])
        for col in inteiros:
            linha[col] = int(linha[col])
    return linhas


def _assert_linhas_iguais(obtidas, esperadas):
    assert len(obtidas) == len(esperadas)
    for obtida, esperada in zip(obtidas, esperadas):
        assert set(obtida) == set(esperada), f"colunas diferem: {obtida.keys()}"
        for col, valor in esperada.items():
            if isinstance(valor, float):
                assert obtida[col] == pytest.approx(valor, abs=0.011), (col, obtida)
            else:
                assert obtida[col] == valor, (col, obtida, esperada)


# ---------------------------------------------------------------------------
# Bloco 1 — TEDs
# ---------------------------------------------------------------------------
def test_ted_rejeitado_fica_fora_do_universo() -> None:
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    teds = calcular_teds(planos, [], [], [])

    assert [t["id_plano_acao"] for t in teds] == ["1"]


def test_ted_membro_nao_identificado_fica_fora() -> None:
    planos = [_plano(1), _plano(-1, situacao="Não identificado")]

    teds = calcular_teds(planos, [], [], [])

    assert [t["id_plano_acao"] for t in teds] == ["1"]


def test_ted_empenhado_liquido_e_bruto_menos_anulado_da_posicao() -> None:
    """Decisão 5: a posição já consolida todas as NEs do plano."""
    planos = [_plano(1429)]
    posicao = [_posicao(1429, bruto=Decimal("1994300.00"), anulado=Decimal("300.00"),
                        qtd_nes=3)]

    [ted] = calcular_teds(planos, posicao, [], [])

    assert ted["empenhado_bruto"] == 1994300.0
    assert ted["empenho_anulado"] == 300.0
    assert ted["empenhado_liquido"] == 1994000.0
    assert ted["qtd_nes"] == 3


def test_ted_pago_soma_exercicio_e_rap_e_liquidado() -> None:
    planos = [_plano(1)]
    posicao = [_posicao(1, liquidado=10, pago=7.5, rap_pago=2.5)]

    [ted] = calcular_teds(planos, posicao, [], [])

    assert ted["liquidado"] == 10.0
    assert ted["pago"] == 10.0


def test_ted_sem_ne_fica_com_zeros() -> None:
    planos = [_plano(1)]
    posicao = [_posicao(1, firmado=Decimal("239652.27"))]

    [ted] = calcular_teds(planos, posicao, [], [])

    assert ted["vl_firmado"] == 239652.27
    assert ted["empenhado_liquido"] == 0.0
    assert ted["pago"] == 0.0
    assert ted["qtd_nes"] == 0


def test_ted_origem_emenda_pela_origem_recurso() -> None:
    """Decisão 6: origem marcada no plano (Emenda quando alguma NE é de emenda)."""
    planos = [
        _plano(2662, origem_recurso="Emenda"),
        _plano(1, origem_recurso="Recurso próprio"),
        _plano(3, origem_recurso="Não identificada"),
    ]

    teds = calcular_teds(planos, [], [], [])

    assert {t["id_plano_acao"]: t["origem"] for t in teds} == {
        "2662": "emenda",
        "1": "orcamento_regular",
        "3": "orcamento_regular",
    }


def test_ted_forma_execucao_2n_e_desagregacao_nao_filtro() -> None:
    """Decisão 4: as flags descrevem, não filtram."""
    planos = [
        _plano(1, execucao_direta=True, execucao_descentralizada=True),
        _plano(2),
    ]

    teds = calcular_teds(planos, [], [], [])

    assert teds[0]["forma_execucao_2n"] == "direta; descentralizada"
    assert teds[1]["forma_execucao_2n"] == ""
    assert len(teds) == 2


def test_ted_aceita_flags_em_texto_como_no_csv_original() -> None:
    planos = [_plano(1, execucao_particulares="SIM")]

    [ted] = calcular_teds(planos, [], [], [])

    assert ted["forma_execucao_2n"] == "particulares"


def test_ted_programa_governo_e_o_de_maior_empenhado() -> None:
    """Decisão 8: programa com maior empenhado nas NEs; empate, menor código."""
    planos = [_plano(1), _plano(2), _plano(3)]
    acoes = [_acao(10, "5804"), _acao(20, "5802"), _acao(30, "5804"), _acao(-1, None)]
    execucao = [
        _ne(1, 10, 100), _ne(1, 20, 300), _ne(1, 30, 50),
        _ne(2, 10, 100), _ne(2, 20, 100),
        _ne(3, -1, 500),
    ]

    teds = calcular_teds(planos, [], execucao, acoes)

    assert [t["programa_governo"] for t in teds] == ["5802", "5802", ""]


def test_ted_etapa_cadeia_vazia_quando_fora_da_definicao_b() -> None:
    """Decisão 7: universos do I1 e da Definição B não coincidem."""
    planos = [_plano(1), _plano(2)]

    teds = calcular_teds(planos, [], [], [], etapa_por_plano={"1": "S4_cadeia_plena"})

    assert teds[0]["etapa_cadeia"] == "S4_cadeia_plena"
    assert teds[1]["etapa_cadeia"] == ""


def test_ted_campos_descritivos() -> None:
    [ted] = calcular_teds([_plano(2532, sq="955606")], [], [], [])

    assert ted["instrumento"] == "TED"
    assert ted["sq_instrumento"] == "955606"
    assert ted["ano"] == "2024"
    assert ted["situacao"] == "APROVADO"
    assert ted["sigla_executor"] == "UFX"
    assert ted["nome_executor"] == "Universidade X"


# ---------------------------------------------------------------------------
# Etapa da cadeia (Definição B) — porte de i1_etapa_cadeia_ted.R
# ---------------------------------------------------------------------------
def test_etapa_cadeia_universo_definicao_b_flag_ou_nc() -> None:
    planos = [
        _plano(1, execucao_descentralizada=True),   # entra pela flag
        _plano(2),                                   # entra pela NC
        _plano(3),                                   # fora
        _plano(-1, execucao_descentralizada=True),   # membro não identificado
    ]
    posicao = [_posicao(2, qtd_nc=1)]

    etapas = classificar_etapa_cadeia(planos, posicao)

    assert set(etapas) == {"1", "2"}


def test_etapa_cadeia_classificacao_por_estagio() -> None:
    planos = [_plano(i, execucao_descentralizada=True) for i in range(1, 6)]
    posicao = [
        _posicao(2, qtd_pf=1),
        _posicao(3, qtd_pf=2, qtd_nc=1),
        _posicao(4, qtd_nc=3),
        _posicao(5, qtd_pf=1, qtd_nc=1, qtd_nes=4),
    ]

    etapas = classificar_etapa_cadeia(planos, posicao)

    assert etapas == {
        "1": "S1_so_plano",
        "2": "S2_ate_PF",
        "3": "S3_ate_NC",
        "4": "S3_NC_sem_PF",
        "5": "S4_cadeia_plena",
    }


# ---------------------------------------------------------------------------
# Bloco 2 — Convênios e termos
# ---------------------------------------------------------------------------
def test_convenio_corte_temporal_2023() -> None:
    fontes = _fontes_convenios([
        _convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01"),
    ])

    convenios = calcular_convenios(**fontes)

    assert [c["nr_convenio"] for c in convenios] == ["2"]
    assert convenios[0]["ano"] == 2023
    assert convenios[0]["ano_fonte"] == "data_assinatura"


def test_convenio_ano_fallback_para_inicio_vigencia() -> None:
    fontes = _fontes_convenios([_convenio(1, assinatura=None, vigencia="2024-05-10")])

    [c] = calcular_convenios(**fontes)

    assert c["ano"] == 2024
    assert c["ano_fonte"] == "inicio_vigencia"


def test_convenio_sem_nenhuma_data_fica_fora() -> None:
    fontes = _fontes_convenios([_convenio(1, assinatura=None, vigencia=None)])

    assert calcular_convenios(**fontes) == []


def test_convenio_aceita_datas_tipadas_do_postgres() -> None:
    fontes = _fontes_convenios([_convenio(1, assinatura=date(2025, 2, 3))])

    [c] = calcular_convenios(**fontes)

    assert c["ano"] == 2025


def test_convenio_exclui_cancelado_e_anulado() -> None:
    fontes = _fontes_convenios([
        _convenio(1, situacao="Cancelado"),
        _convenio(2, situacao="Convênio Anulado"),
        _convenio(3, situacao="Convenio Anulado"),
        _convenio(4, situacao="Aguardando Prestação de Contas"),
    ])

    convenios = calcular_convenios(**fontes)

    assert [c["nr_convenio"] for c in convenios] == ["4"]


def test_convenio_origem_emenda_pela_origem_recurso() -> None:
    fontes = _fontes_convenios([
        _convenio(1, origem="Emenda"),
        _convenio(2, origem="Recurso próprio"),
        _convenio(3, origem="Não identificada"),
    ])

    convenios = calcular_convenios(**fontes)

    assert [c["origem"] for c in convenios] == [
        "emenda", "orcamento_regular", "orcamento_regular",
    ]


def test_convenio_sem_empenho_permanece_na_contagem() -> None:
    """Decisão 3c: empenhado zero/vazio fica no universo, marcado."""
    fontes = _fontes_convenios([
        _convenio(1, empenhado=None), _convenio(2, empenhado=Decimal("300000.00")),
    ])

    convenios = calcular_convenios(**fontes)

    assert [c["sem_empenho"] for c in convenios] == [1, 0]
    assert convenios[0]["empenhado_liquido"] == 0.0
    assert convenios[1]["empenhado_liquido"] == 300000.0


def test_convenio_campos_descritivos_vem_da_posicao_e_das_dimensoes() -> None:
    fontes = _fontes_convenios([_convenio(972607, modalidade="TERMO DE FOMENTO")])

    [c] = calcular_convenios(**fontes)

    assert c["instrumento"] == "TERMO DE FOMENTO"
    assert c["nr_convenio"] == "972607"
    assert c["uf_execucao"] == "DF"
    assert c["municipio_execucao"] == "BRASÍLIA"
    assert c["convenente"] == "Prefeitura"
    assert c["categoria_convenente"] == "Administração Pública Municipal"
    assert c["vl_firmado"] == 200.0
    assert c["pago"] == 50.0


def test_convenio_membro_nao_identificado_fica_fora() -> None:
    fontes = _fontes_convenios([_convenio(1)])
    fontes["convenios"].append({
        "sk_convenio": -1, "nr_convenio": "-1", "modalidade": "Não identificado",
        "origem_recurso": "Não identificada", "situacao": "Não identificado",
        "data_assinatura": "2024-01-01", "data_inicio_vigencia": None,
    })

    convenios = calcular_convenios(**fontes)

    assert [c["nr_convenio"] for c in convenios] == ["1"]


# ---------------------------------------------------------------------------
# Agregações — regressão contra os resultados entregues pelo BI
# ---------------------------------------------------------------------------
CONV_NUM = ("vl_firmado", "empenhado_liquido", "pago")
CONV_INT = ("sem_empenho",)
AGG_INT = ("n_instrumentos", "n_sem_empenho", "n_emenda", "n_regular")
AGG_NUM = ("vl_firmado", "empenhado_liquido", "pago", "share_pct")


def test_regressao_convenios_por_uf() -> None:
    convenios = _ler_fixture("i1_convenios_por_instrumento.csv", CONV_NUM, CONV_INT)
    esperado = _ler_fixture("i1_convenios_por_uf.csv", AGG_NUM, AGG_INT)

    _assert_linhas_iguais(agregar_convenios_por_uf(convenios), esperado)


def test_regressao_convenios_por_municipio() -> None:
    convenios = _ler_fixture("i1_convenios_por_instrumento.csv", CONV_NUM, CONV_INT)
    esperado = _ler_fixture("i1_convenios_por_municipio.csv", AGG_NUM, AGG_INT)

    _assert_linhas_iguais(agregar_convenios_por_municipio(convenios), esperado)


def test_regressao_teds_por_executor() -> None:
    teds = _ler_fixture(
        "i1_ted_por_instrumento.csv",
        ("vl_firmado", "empenhado_bruto", "empenho_anulado", "empenhado_liquido",
         "liquidado", "pago"),
        ("n_linhas_resumo",),
    )
    esperado = _ler_fixture(
        "i1_ted_por_executor.csv",
        ("vl_firmado", "empenhado_liquido", "pago", "share_pct"),
        ("n_teds", "n_sem_empenho"),
    )

    _assert_linhas_iguais(agregar_teds_por_executor(teds), esperado)


def test_territorio_nao_informado_vira_rotulo_explicito() -> None:
    fontes = _fontes_convenios([_convenio(1, uf=None, municipio="")])
    convenios = calcular_convenios(**fontes)

    [uf] = agregar_convenios_por_uf(convenios)
    [mun] = agregar_convenios_por_municipio(convenios)

    assert uf["uf_execucao"] == "NAO_INFORMADO"
    assert mun["municipio_execucao"] == "NAO_INFORMADO"
    assert mun["uf_execucao"] == "NAO_INFORMADO"


# ---------------------------------------------------------------------------
# Leitura 1 — carteira por instrumento e origem
# ---------------------------------------------------------------------------
def test_carteira_agrega_ted_e_convenios_por_tipo_e_origem() -> None:
    teds = calcular_teds(
        [_plano(1, origem_recurso="Emenda"), _plano(2)],
        [_posicao(1, bruto=600), _posicao(2, bruto=200)],
        [],
        [],
    )
    convenios = calcular_convenios(**_fontes_convenios([
        _convenio(1, empenhado=100, origem="Emenda"),
        _convenio(2, empenhado=100, origem="Emenda"),
    ]))

    carteira = calcular_carteira(teds, convenios)

    assert [(c["instrumento"], c["origem"], c["n_instrumentos"]) for c in carteira] == [
        ("TED", "emenda", 1),
        ("TED", "orcamento_regular", 1),
        ("CONVENIO", "emenda", 2),
    ]
    assert [c["share_pct"] for c in carteira] == [60.0, 20.0, 20.0]
    assert all(c["leitura"] == "carteira_sem_territorio" for c in carteira)


def test_carteira_share_zero_quando_nao_ha_empenho() -> None:
    carteira = calcular_carteira(calcular_teds([_plano(1)], [], [], []), [])

    assert carteira[0]["share_pct"] == 0


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i1_devolve_as_seis_saidas() -> None:
    saidas = calcular_i1(
        planos=[_plano(1, execucao_descentralizada=True)],
        posicao_planos=[_posicao(1, bruto=10, qtd_pf=1)],
        execucao_teds=[],
        acoes_teds=[],
        **_fontes_convenios([_convenio(1)]),
    )

    assert set(saidas) == {
        "i1_ted_por_instrumento",
        "i1_ted_por_executor",
        "i1_convenios_por_instrumento",
        "i1_convenios_por_uf",
        "i1_convenios_por_municipio",
        "i1_valor_por_instrumento",
    }
    assert saidas["i1_ted_por_instrumento"][0]["etapa_cadeia"] == "S2_ate_PF"
    assert len(saidas["i1_valor_por_instrumento"]) == 2
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `python3 -m pytest tests/test_plugins/test_indicadores_i1.py -q -p no:cacheprovider 2>&1 | grep -E "passed|failed"`
Expected: FAIL. Os testes de TED e de convênio falham com `TypeError`, porque as funções ainda têm as assinaturas antigas. Os 3 testes de regressão (`test_regressao_*`) passam.

- [ ] **Step 3: Reescrever o plugin**

Em `airflow_lappis/plugins/indicadores/i1_valor_executado.py`:

1. Substituir o docstring do módulo (linhas 1–36) por:

```python
"""Indicador I1 — Valor Executado por Instrumento.

Porte de ``i1_valor_executado.py`` e ``i1_etapa_cadeia_ted.R`` (equipe de BI,
2026-07-21) para funções puras. A lógica e as decisões metodológicas são as
do script original; os dados vêm dos data marts ``mir_teds`` e
``mir_convenios`` (remodelagem fato-dimensão do dbt MIR, etapa 5).

    Leitura 1 — valor por instrumento (TED + convênio + fomento), SEM território
    Leitura 2 — valor por território (UF e município), SOMENTE convênios/fomentos

Fontes (tabelas do dbt):
    mir_teds.dim_plano_acao              → cadastro dos TEDs e origem do recurso
    mir_teds.fato_plano_acao_posicao     → valores por TED e quantidades de PF/NC/NE
    mir_teds.fato_execucao_orcamentaria  → NEs por TED (programa de governo)
    mir_teds.dim_acao_orcamentaria       → programa de cada PTRES
    mir_convenios.dim_convenio           → cadastro dos convênios/fomentos
    mir_convenios.fato_convenio_posicao  → valores por convênio
    mir_convenios.dim_convenente         → convenente
    mir_convenios.dim_localidade         → UF e município de execução

As dimensões se ligam às posições pelas chaves ``sk_*``; o membro ``-1``
("Não identificado") das dimensões não entra no universo.

Decisões metodológicas (resumo; o detalhe está no script original):
 1. Duas leituras separadas: TED fica FORA da leitura territorial, porque a
    única UF disponível é a sede do executor, não o território atendido.
 2. Convênios vêm de fato_convenio_posicao (grão: um instrumento por linha).
    O tipo é a ``modalidade``, a origem é ``origem_recurso`` (Emenda quando
    alguma NE do instrumento é de emenda) e o empenhado é o registrado no
    SICONV (``valor_empenhado_siconv``, a mesma medida do gold antigo).
 3. Universo dos convênios: ano >= 2023 (data_assinatura, fallback
    data_inicio_vigencia); excluídos Cancelado/Anulado; empenhado zero
    permanece na contagem, marcado em ``sem_empenho``.
 4. Universo dos TEDs: todos os planos exceto REJEITADO. As flags
    ``execucao_*`` desagregam, não filtram.
 5. Empenhado do TED vem da posição do plano: bruto, anulado e líquido já
    consolidam todas as NEs ligadas ao plano.
 6. Origem do TED: ``origem_recurso`` da dim_plano_acao.
 7. Etapa da cadeia sob a Definição B (TED = flag descentralizada OU tem NC),
    pelas quantidades de PF, NC e NE da posição; TEDs fora dela ficam com
    ``etapa_cadeia`` vazia.
 8. Programa de governo do TED: o programa com maior empenhado nas NEs do
    plano (empate: menor código); vazio se o plano não tem NE.
"""
```

2. Logo depois de `ROTULO_NAO_INFORMADO = "NAO_INFORMADO"`, acrescentar:

```python
MEMBRO_NAO_IDENTIFICADO = "-1"
ORIGEM_EMENDA = "Emenda"
```

3. Logo depois da função `_ids` (que passa a não ser usada e é removida), no lugar dela, colocar:

```python
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

4. Substituir `classificar_etapa_cadeia` por:

```python
def classificar_etapa_cadeia(
    planos: list[dict], posicao_planos: list[dict]
) -> dict[str, str]:
    """Estágio no funil PF → NC → NE por TED, sob a Definição B.

    Universo: plano com flag ``execucao_descentralizada`` OU com NC na
    posição. Retorna ``{id_plano_acao: estagio}``.
    """
    posicao = _por_chave(posicao_planos, "sk_plano_acao")

    etapas: dict[str, str] = {}
    for p in _membros(planos, "sk_plano_acao"):
        pid = _txt(p.get("id_plano_acao"))
        pos = posicao.get(p.get("sk_plano_acao"), {})
        tem_pf = _num(pos.get("qtd_pf")) > 0
        tem_nc = _num(pos.get("qtd_nc")) > 0
        tem_ne = _num(pos.get("qtd_nes")) > 0
        if not (_flag(p.get("execucao_descentralizada")) or tem_nc):
            continue
        if tem_pf and tem_nc and tem_ne:
            etapas[pid] = "S4_cadeia_plena"
        elif tem_pf and tem_nc:
            etapas[pid] = "S3_ate_NC"
        elif tem_pf:
            etapas[pid] = "S2_ate_PF"
        elif tem_nc:
            etapas[pid] = "S3_NC_sem_PF"
        else:
            etapas[pid] = "S1_so_plano"
    return etapas
```

5. Substituir `calcular_teds` por:

```python
def _programa_por_plano(
    execucao_teds: list[dict], acoes_teds: list[dict]
) -> dict[Any, str]:
    """Programa de governo com maior empenhado nas NEs de cada plano."""
    programa_da_acao = {
        a.get("sk_acao_orcamentaria"): _txt(a.get("codigo_programa")) for a in acoes_teds
    }
    empenhado: dict[tuple, float] = defaultdict(float)
    for r in execucao_teds:
        programa = programa_da_acao.get(r.get("sk_acao_orcamentaria"), "")
        if programa:
            chave = (r.get("sk_plano_acao"), programa)
            empenhado[chave] += _num(r.get("despesas_empenhadas"))

    escolhido: dict[Any, str] = {}
    for (sk_plano, programa), _valor in sorted(
        empenhado.items(), key=lambda x: (-x[1], x[0][1])
    ):
        escolhido.setdefault(sk_plano, programa)
    return escolhido


def calcular_teds(
    planos: list[dict],
    posicao_planos: list[dict],
    execucao_teds: list[dict],
    acoes_teds: list[dict],
    etapa_por_plano: dict[str, str] | None = None,
) -> list[dict]:
    etapa_por_plano = etapa_por_plano or {}
    posicao = _por_chave(posicao_planos, "sk_plano_acao")
    programa_por_plano = _programa_por_plano(execucao_teds, acoes_teds)

    teds = []
    for p in _membros(planos, "sk_plano_acao"):
        situacao = _txt(p.get("situacao"))
        if situacao in SITUACOES_EXCLUIDAS_TED:
            continue

        sk = p.get("sk_plano_acao")
        pid = _txt(p.get("id_plano_acao"))
        pos = posicao.get(sk, {})

        empenhado = _num(pos.get("empenhado_bruto"))
        anulado = _num(pos.get("empenho_anulado"))
        pago = _num(pos.get("despesas_pagas")) + _num(pos.get("restos_a_pagar_pagos"))
        formas = [
            nome
            for nome, campo in (
                ("direta", "execucao_direta"),
                ("particulares", "execucao_particulares"),
                ("descentralizada", "execucao_descentralizada"),
            )
            if _flag(p.get(campo))
        ]

        teds.append({
            "id_plano_acao": pid,
            "sq_instrumento": _txt(p.get("num_transf")),
            "instrumento": "TED",
            "origem": _origem(p),
            "ano": _txt(p.get("ano")),
            "situacao": situacao,
            "sigla_executor": _txt(p.get("sigla_unidade_descentralizada")),
            "nome_executor": _txt(p.get("unidade_descentralizada")),
            "programa_governo": programa_por_plano.get(sk, ""),
            "etapa_cadeia": etapa_por_plano.get(pid, ""),
            "forma_execucao_2n": "; ".join(formas),
            "vl_firmado": round(_num(pos.get("valor_firmado")), 2),
            "empenhado_bruto": round(empenhado, 2),
            "empenho_anulado": round(anulado, 2),
            "empenhado_liquido": round(empenhado - anulado, 2),
            "liquidado": round(_num(pos.get("despesas_liquidadas")), 2),
            "pago": round(pago, 2),
            "qtd_nes": int(_num(pos.get("qtd_nes"))),
        })
    return teds
```

6. Substituir `_ano_instrumento` e `calcular_convenios` por:

```python
def _ano_instrumento(r: dict) -> tuple[int | None, str | None]:
    """Ano de referência: data_assinatura, com fallback para o início da vigência."""
    for campo, rotulo in (
        ("data_assinatura", "data_assinatura"),
        ("data_inicio_vigencia", "inicio_vigencia"),
    ):
        ano = _ano(r.get(campo))
        if ano is not None:
            return ano, rotulo
    return None, None


def calcular_convenios(
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
    localidades: list[dict],
    ano_corte: int = ANO_CORTE,
) -> list[dict]:
    posicao = _por_chave(posicao_convenios, "sk_convenio")
    convenente_por_sk = _por_chave(convenentes, "sk_convenente")
    localidade_por_sk = _por_chave(localidades, "sk_localidade")

    saida = []
    for r in _membros(convenios, "sk_convenio"):
        ano, ano_fonte = _ano_instrumento(r)
        if ano is None or ano < ano_corte:
            continue
        situacao = _txt(r.get("situacao"))
        if situacao in SITUACOES_EXCLUIDAS_CONVENIO:
            continue

        pos = posicao.get(r.get("sk_convenio"), {})
        convenente = convenente_por_sk.get(pos.get("sk_convenente"), {})
        localidade = localidade_por_sk.get(pos.get("sk_localidade"), {})
        empenhado = _num(pos.get("valor_empenhado_siconv"))
        saida.append({
            "nr_convenio": _txt(r.get("nr_convenio")),
            "instrumento": _txt(r.get("modalidade")),
            "origem": _origem(r),
            "ano": ano,
            "ano_fonte": ano_fonte,
            "situacao": situacao,
            "uf_execucao": _txt(localidade.get("uf")),
            "municipio_execucao": _txt(localidade.get("municipio")),
            "convenente": _txt(convenente.get("convenente_nome")),
            "categoria_convenente": _txt(convenente.get("convenente_natureza_juridica")),
            "vl_firmado": round(_num(pos.get("valor_firmado_atualizado")), 2),
            "empenhado_liquido": round(empenhado, 2),
            "pago": round(_num(pos.get("valor_pago_fornecedores")), 2),
            "sem_empenho": 1 if empenhado == 0 else 0,
        })
    return saida
```

7. Substituir `calcular_i1` por:

```python
def calcular_i1(
    planos: list[dict],
    posicao_planos: list[dict],
    execucao_teds: list[dict],
    acoes_teds: list[dict],
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
    localidades: list[dict],
) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I1 a partir das tabelas dos marts."""
    etapas = classificar_etapa_cadeia(planos, posicao_planos)
    teds = calcular_teds(planos, posicao_planos, execucao_teds, acoes_teds, etapas)
    convenios_i1 = calcular_convenios(
        convenios, posicao_convenios, convenentes, localidades
    )
    return {
        "i1_ted_por_instrumento": teds,
        "i1_ted_por_executor": agregar_teds_por_executor(teds),
        "i1_convenios_por_instrumento": convenios_i1,
        "i1_convenios_por_uf": agregar_convenios_por_uf(convenios_i1),
        "i1_convenios_por_municipio": agregar_convenios_por_municipio(convenios_i1),
        "i1_valor_por_instrumento": calcular_carteira(teds, convenios_i1),
    }
```

As funções `agregar_teds_por_executor`, `_agregar_territorio`, `agregar_convenios_por_uf`, `agregar_convenios_por_municipio` e `calcular_carteira` ficam como estão.

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `python3 -m pytest tests/test_plugins/test_indicadores_i1.py -q -p no:cacheprovider 2>&1 | grep -E "passed|failed"`
Expected: `29 passed`.

Run: `grep -n "_ids\|n_linhas_resumo\|ted_resumo\|instrumentos_emendas\|gold_convenios\|in_forma_execucao" airflow_lappis/plugins/indicadores/i1_valor_executado.py`
Expected: nenhuma linha.

- [ ] **Step 5: Commit**

```bash
git add -- airflow_lappis/plugins/indicadores/i1_valor_executado.py tests/test_plugins/test_indicadores_i1.py
git commit -m "feat(indicadores): I1 le os marts mir_teds e mir_convenios" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" \
  -- airflow_lappis/plugins/indicadores/i1_valor_executado.py tests/test_plugins/test_indicadores_i1.py
```

---

### Task 2: DAG do I1 e paridade com o I1 antigo

**Files:**
- Modify: `airflow_lappis/dags/indicadores/mir/i1_valor_executado_dag.py:12-21` e o docstring da DAG
- Modify: este plano (seção "Resultado da paridade do I1")
- Scratch (não commitado): `$SP/i1_antigo.py`, `$SP/i1_paridade.py`, com `SP=/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad`

**Interfaces:**
- Consumes: `calcular_i1(planos, posicao_planos, execucao_teds, acoes_teds, convenios, posicao_convenios, convenentes, localidades)` da Tarefa 1.

- [ ] **Step 1: Apontar o `FONTES` para os marts**

Em `i1_valor_executado_dag.py`, substituir o bloco `FONTES` por:

```python
# Tabelas dbt lidas pelo indicador -> nome do argumento de calcular_i1
FONTES = {
    "planos": ("mir_teds", "dim_plano_acao"),
    "posicao_planos": ("mir_teds", "fato_plano_acao_posicao"),
    "execucao_teds": ("mir_teds", "fato_execucao_orcamentaria"),
    "acoes_teds": ("mir_teds", "dim_acao_orcamentaria"),
    "convenios": ("mir_convenios", "dim_convenio"),
    "posicao_convenios": ("mir_convenios", "fato_convenio_posicao"),
    "convenentes": ("mir_convenios", "dim_convenente"),
    "localidades": ("mir_convenios", "dim_localidade"),
}
```

e, no docstring da função da DAG, trocar `Lê as tabelas dbt (TED, convênios, emendas)` por `Lê os data marts mir_teds e mir_convenios`.

Run: `grep -n "_validate_identifiers" -A4 airflow_lappis/plugins/cliente_postgres.py`
Expected: a validação aceita nomes em minúsculas com `_` (os schemas `mir_teds` e `mir_convenios` passam). Se a regex não aceitar, parar e reportar.

Run: `python3 -c "import ast,sys; ast.parse(open('airflow_lappis/dags/indicadores/mir/i1_valor_executado_dag.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 2: Montar o comparador antigo × novo**

```bash
SP=/tmp/claude-1000/-home-joaoegewarth-data-application-mir/045972ee-3d86-4b2e-83b0-df2ae824d86f/scratchpad
git show d285ffe:airflow_lappis/plugins/indicadores/i1_valor_executado.py > $SP/i1_antigo.py
```

Criar `$SP/i1_paridade.py`:

```python
"""Compara o I1 antigo (gold antigo) com o novo (marts) no dump local."""

import sys
from collections import Counter
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, "/home/joaoegewarth/data-application-mir/airflow_lappis/plugins")
sys.path.insert(0, str(Path(__file__).parent))  # i1_antigo.py fica ao lado

import i1_antigo  # noqa: E402
from indicadores import i1_valor_executado as i1_novo  # noqa: E402

conn = psycopg2.connect(host="localhost", port=5433, user="postgres",
                        password="postgres", dbname="analytics")


def tabela(schema, nome):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"select * from {schema}.{nome}")
        return [dict(r) for r in cur.fetchall()]


antigo = i1_antigo.calcular_i1(
    planos=tabela("siafi_dbt", "planos_acao_ted"),
    resumo=tabela("siafi_dbt", "ted_resumo_orcamentario"),
    pf=tabela("siafi_dbt", "pf_unificado_planos_acao"),
    nc=tabela("siafi_dbt", "nc_plano_acao"),
    ne=tabela("siafi_dbt", "ted_empenhos_plano_acao"),
    gold_convenios=tabela("siconv_dbt", "resumo_convenios"),
    instrumentos_emendas=tabela("emendas", "instrumentos_emendas"),
)
novo = i1_novo.calcular_i1(
    planos=tabela("mir_teds", "dim_plano_acao"),
    posicao_planos=tabela("mir_teds", "fato_plano_acao_posicao"),
    execucao_teds=tabela("mir_teds", "fato_execucao_orcamentaria"),
    acoes_teds=tabela("mir_teds", "dim_acao_orcamentaria"),
    convenios=tabela("mir_convenios", "dim_convenio"),
    posicao_convenios=tabela("mir_convenios", "fato_convenio_posicao"),
    convenentes=tabela("mir_convenios", "dim_convenente"),
    localidades=tabela("mir_convenios", "dim_localidade"),
)

for saida in antigo:
    print(f"{saida}: antigo {len(antigo[saida])} linhas, novo {len(novo[saida])} linhas")


def comparar(nome, chave, campos):
    a_linhas, n_linhas = antigo[nome], novo[nome]
    repetidas = {k: c for k, c in Counter(r[chave] for r in a_linhas).items() if c > 1}
    a = {r[chave]: r for r in a_linhas}
    n = {r[chave]: r for r in n_linhas}
    print(f"\n== {nome}: {len(repetidas)} chaves repetidas no antigo "
          f"({sum(repetidas.values()) - len(repetidas)} linhas a mais)")
    print(f"   só no antigo: {sorted(set(a) - set(n))}")
    print(f"   só no novo:   {sorted(set(n) - set(a))}")
    for campo in campos:
        difs = [(k, a[k][campo], n[k][campo]) for k in sorted(set(a) & set(n))
                if a[k][campo] != n[k][campo]]
        print(f"   {campo}: {len(difs)} diferentes")
        for k, va, vn in difs:
            print(f"      {k}: {va!r} -> {vn!r}")


comparar("i1_ted_por_instrumento", "id_plano_acao",
         ["sq_instrumento", "origem", "ano", "situacao", "sigla_executor",
          "programa_governo", "etapa_cadeia", "forma_execucao_2n", "vl_firmado",
          "empenhado_bruto", "empenho_anulado", "empenhado_liquido", "liquidado", "pago"])
comparar("i1_convenios_por_instrumento", "nr_convenio",
         ["instrumento", "origem", "ano", "ano_fonte", "situacao", "uf_execucao",
          "municipio_execucao", "convenente", "categoria_convenente", "vl_firmado",
          "empenhado_liquido", "pago", "sem_empenho"])

print("\n== i1_valor_por_instrumento (instrumento, origem): antigo -> novo")
chave = lambda r: (r["instrumento"], r["origem"])  # noqa: E731
ca = {chave(r): r for r in antigo["i1_valor_por_instrumento"]}
cn = {chave(r): r for r in novo["i1_valor_por_instrumento"]}
for k in sorted(set(ca) | set(cn)):
    va, vn = ca.get(k, {}), cn.get(k, {})
    print(f"   {k}: n {va.get('n_instrumentos')} -> {vn.get('n_instrumentos')}; "
          f"empenhado {va.get('empenhado_liquido')} -> {vn.get('empenhado_liquido')}; "
          f"pago {va.get('pago')} -> {vn.get('pago')}")
```

- [ ] **Step 3: Rodar a paridade**

Run: `cd /home/joaoegewarth/data-application-mir && python3 $SP/i1_paridade.py > $SP/i1_paridade.txt 2>&1; tail -n +1 $SP/i1_paridade.txt | head -200`
Expected: roda sem erro e imprime as seis saídas, as diferenças por campo e a carteira. As diferenças esperadas, que precisam ser confirmadas uma a uma:
- **Convênios repetidos no antigo:** `resumo_convenios` tem 834 linhas para 643 convênios; o I1 antigo contava cada repetição como instrumento. O novo tem um convênio por linha.
- **Origem de convênio:** 23 convênios de 2023 em diante passam a `emenda` (NE de emenda no núcleo, sem parlamentar no SICONV).
- **TEDs:** empenhado/liquidado/pago mudam onde o núcleo liga NEs que a cascata antiga não ligava (ex.: planos 4407 e 2932) ou deixa de somar NCs internas do MIR; origem muda onde `instrumentos_emendas` e o núcleo discordam; `etapa_cadeia` muda onde NC/PF/NE passaram a ser ligadas ao plano pelas regras novas; `programa_governo` pode mudar nos 5 planos com mais de um programa.

Toda diferença fora dessas causas é investigada antes de seguir (consultar o plano ou convênio nas tabelas antigas e novas). Uma diferença sem causa conhecida é regressão: parar e reportar.

- [ ] **Step 4: Registrar o resultado**

Acrescentar ao fim deste plano a seção `## Resultado da paridade do I1 (2026-09-29)` com: contagem de linhas de cada saída (antigo → novo); a tabela da carteira (instrumento, origem, n, empenhado, pago; antigo → novo); e a lista de diferenças por instrumento, agrupada pela causa, com os números de plano/convênio.

- [ ] **Step 5: Commit**

```bash
git add -- airflow_lappis/dags/indicadores/mir/i1_valor_executado_dag.py docs/superpowers/plans/2026-09-29-etapa-5-i1-e-remocao.md
git commit -m "feat(indicadores): DAG do I1 le os marts; paridade com o I1 antigo" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" \
  -- airflow_lappis/dags/indicadores/mir/i1_valor_executado_dag.py docs/superpowers/plans/2026-09-29-etapa-5-i1-e-remocao.md
```

---

### Task 3: Remover os modelos antigos do dbt

**Files:**
- Remove: 41 modelos e seus `schema.yml` (lista em Global Constraints), 3 análises de paridade, 3 testes antigos
- Modify: `models/emendas_dbt/silver/schema.yml`, comentários listados em File Structure, `.claude/skills/govhub-pipeline-guide/SKILL.md:542`

Todos os caminhos abaixo são relativos a `airflow_lappis/dags/dbt/mir/`, exceto o `SKILL.md`.

- [ ] **Step 1: Remover os arquivos**

```bash
cd /home/joaoegewarth/data-application-mir/airflow_lappis/dags/dbt/mir
git rm -q -r models/siconv_dbt/silver models/siconv_dbt/gold \
  models/empenhos_ted_dbt/silver models/empenhos_ted_dbt/views models/empenhos_ted_dbt/gold \
  models/emendas_dbt/gold
git rm -q models/emendas_dbt/silver/emendas_orcamento_execucao.sql \
  models/emendas_dbt/silver/emendas_partidos.sql \
  models/emendas_dbt/silver/instrumentos_emendas.sql \
  analyses/paridade_mir_convenios.sql analyses/paridade_mir_teds.sql analyses/paridade_mir_emendas.sql \
  tests/test_ted_resumo_orcamentario_grao_unico.sql \
  tests/test_ted_resumo_orcamentario_reconciliacao_empenhado.sql \
  tests/test_num_transf_n_plano_acao_cardinalidade.sql
ls models/emendas_dbt/silver models/siconv_dbt models/empenhos_ted_dbt models/emendas_dbt
```

Expected: `models/emendas_dbt/silver` tem só `planos_partidos.sql` e `schema.yml`; `models/siconv_dbt`, `models/empenhos_ted_dbt` e `models/emendas_dbt` têm só `bronze` (e `silver`, no caso de `emendas_dbt`).

- [ ] **Step 2: Deixar no `schema.yml` de `emendas_dbt/silver` só o `planos_partidos`**

O bloco do `planos_partidos` vai da linha 5 até antes de `  - name: emendas_partidos` (linha 167). Cortar o arquivo ali:

```bash
python3 - <<'EOF'
p = "models/emendas_dbt/silver/schema.yml"
linhas = open(p).read().split("\n")
corte = linhas.index("  - name: emendas_partidos")
assert linhas[4] == "  - name: planos_partidos", linhas[4]
assert all(not l.startswith("  - name: ") for l in linhas[5:corte])
open(p, "w").write("\n".join(linhas[:corte]).rstrip() + "\n")
EOF
tail -3 models/emendas_dbt/silver/schema.yml
```

Expected: termina no teste `verificacao_tipagem` de `emendas.planos_partidos.dt_ingest` (`tipo_esperado: 'timestamp with time zone'`).

- [ ] **Step 3: Atualizar os comentários que citam modelos removidos como existentes**

- `macros/star_except.sql`: `identificadores em empenhos_por_plano_acao.sql.` → `identificadores em mir_silver/ted_ne_transferencia.sql.`
- `macros/mir_silver/parlamentar_na_data.sql`: `parlamentares_historico, com as prioridades do emendas_partidos:` → `parlamentares_historico, com as prioridades do antigo emendas_partidos:`
- `models/mir_silver/schema.yml` (descrição de `emenda_ne`): `autor com o partido vigente na data de emissao da NE, pelas prioridades do` / `emendas_partidos (1 = ...` → `autor com o partido vigente na data de emissao da NE, pelas prioridades do` / `antigo emendas_partidos (1 = ...` (só acrescentar `antigo `, mantendo a quebra de linha do YAML).
- `models/mir_silver/convenio_mir.sql` (linhas 3–4): `-- Universo de convenios do MIR no SICONV, no grao do instrumento. Mesmo` / `-- recorte de convenios_consolidados: ug_emitente 810008 ou com NE da UG 810008` → `-- Universo de convenios do MIR no SICONV, no grao do instrumento. Mesmo` / `-- recorte do antigo convenios_consolidados: ug_emitente 810008 ou com NE da UG 810008`
- `models/mir_silver/vinculo_ne_convenio.sql` (linha 4): `-- Mesma regra de convenio usada hoje em numero_transferencia, mas aplicada a` → `-- Mesma regra de convenio do antigo numero_transferencia, mas aplicada a`
- `models/mir_silver/ted_ne_transferencia.sql` (linhas 547–549):

```sql
-- A resolucao do plano de acao fica fora da cascata: vinculo_ne_ted resolve
-- pelo sq_instrumento do plano, e o modelo antigo empenhos_por_plano_acao pela
-- ponte num_transf_n_plano_acao.
```

vira

```sql
-- A resolucao do plano de acao fica fora da cascata: vinculo_ne_ted resolve
-- pelo sq_instrumento do plano.
```

- `.claude/skills/govhub-pipeline-guide/SKILL.md:542`: `| Silver com joins | \`models/siconv_dbt/silver/proposta_convenio.sql\` |` → `| Silver com regra de negócio | \`models/mir_silver/convenio_mir.sql\` |`

Run: `grep -rnwE "convenios_consolidados|emendas_partidos|empenhos_por_plano_acao|numero_transferencia|num_transf_n_plano_acao|resumo_convenios|ted_resumo_orcamentario|proposta_convenio" models macros tests analyses ../../../../.claude/skills | grep -vE "antigo|Movida de"`
Expected: nenhuma linha.

- [ ] **Step 4: Verificar o projeto sem os modelos antigos**

```bash
dbt parse --profiles-dir . --no-partial-parse 2>&1 | grep -E "WARNING|ERROR|Error" | grep -v "termo_fomento"
dbt ls --profiles-dir . --no-partial-parse --resource-type model --output path 2>/dev/null \
  | grep -E "siconv_dbt/(silver|gold)|empenhos_ted_dbt/(silver|views|gold)|emendas_dbt/(silver|gold)"
```

Expected: nenhum erro; o `dbt ls` lista só `models/emendas_dbt/silver/planos_partidos.sql`.

Run: `dbt build --profiles-dir . --no-partial-parse -s path:models/mir_silver path:models/mir_convenios path:models/mir_teds path:models/mir_emendas 2>&1 | grep -E "WARN |ERROR|FAIL|Done\."`
Expected: `ERROR=0`. O único `WARN` é o esperado do complemento próprio (`convenio_mir_complemento_proprio`).

Run (da raiz): `$SQLFMT --check airflow_lappis/dags/dbt/mir/macros/star_except.sql airflow_lappis/dags/dbt/mir/macros/mir_silver/parlamentar_na_data.sql airflow_lappis/dags/dbt/mir/models/mir_silver/convenio_mir.sql airflow_lappis/dags/dbt/mir/models/mir_silver/vinculo_ne_convenio.sql airflow_lappis/dags/dbt/mir/models/mir_silver/ted_ne_transferencia.sql`, com `SQLFMT` = o caminho do sqlfmt no Ambiente local.
Expected: `5 files passed formatting check.` Se o `star_except.sql` ou o `ted_ne_transferencia.sql` já não passavam antes da mudança (`git stash` não pode ser usado por causa do stage do `dicionario-mir/`; conferir com `git show HEAD:<arquivo> | $SQLFMT --check -`), registrar e seguir sem formatar o arquivo inteiro.

- [ ] **Step 5: Commit**

```bash
cd /home/joaoegewarth/data-application-mir
P=airflow_lappis/dags/dbt/mir
git add -- $P/models/emendas_dbt/silver/schema.yml $P/macros/star_except.sql \
  $P/macros/mir_silver/parlamentar_na_data.sql $P/models/mir_silver/schema.yml \
  $P/models/mir_silver/convenio_mir.sql $P/models/mir_silver/vinculo_ne_convenio.sql \
  $P/models/mir_silver/ted_ne_transferencia.sql .claude/skills/govhub-pipeline-guide/SKILL.md
git commit -m "refactor(dbt/mir): remove a silver e o gold antigos substituidos pelos marts" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" \
  -- $P/models/siconv_dbt/silver $P/models/siconv_dbt/gold $P/models/empenhos_ted_dbt/silver \
     $P/models/empenhos_ted_dbt/views $P/models/empenhos_ted_dbt/gold $P/models/emendas_dbt/gold \
     $P/models/emendas_dbt/silver $P/analyses $P/tests/test_ted_resumo_orcamentario_grao_unico.sql \
     $P/tests/test_ted_resumo_orcamentario_reconciliacao_empenhado.sql \
     $P/tests/test_num_transf_n_plano_acao_cardinalidade.sql \
     $P/macros/star_except.sql $P/macros/mir_silver/parlamentar_na_data.sql \
     $P/models/mir_silver/schema.yml $P/models/mir_silver/convenio_mir.sql \
     $P/models/mir_silver/vinculo_ne_convenio.sql $P/models/mir_silver/ted_ne_transferencia.sql \
     .claude/skills/govhub-pipeline-guide/SKILL.md
git show --stat HEAD | tail -3
git diff --cached --name-only | grep -vc '^dicionario-mir/'
```

Expected: o commit tem as remoções e as 8 modificações; o último comando imprime `0`.

---

### Task 4: Script de drop, guia do Power BI e fechamento

**Files:**
- Create: `docs/mir-drop-legado.sql`
- Create: `docs/mir-guia-migracao-power-bi.md`
- Modify: `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md` (§9, §10, §12, §13)

- [ ] **Step 1: Escrever o script de drop**

Criar `docs/mir-drop-legado.sql`:

```sql
-- Remove do banco as tabelas da silver e do gold antigos do MIR, substituidos
-- pelos marts mir_convenios, mir_teds e mir_emendas (remodelagem fato-dimensao,
-- etapa 5). Os modelos ja sairam do dbt: essas tabelas estao paradas desde o
-- deploy. Rodar so depois de migrar os paineis do Power BI
-- (docs/mir-guia-migracao-power-bi.md).
--
-- Sem cascade: se um painel ou view ainda depender de uma tabela, o drop falha
-- e a transacao inteira volta atras. O planos_partidos (emendas PIX) fica.
begin;

drop view siafi_dbt.num_transf_n_plano_acao;

drop table emendas.emendas_execucao_por_ug;
drop table emendas.emendas_instrumentos_execucao;
drop table emendas.emendas_orcamento_execucao;
drop table emendas.emendas_partidos;
drop table emendas.instrumentos_emendas;
drop table emendas.resumo_emendas_orcamento_execucao;

drop table siafi_dbt.empenhos_por_plano_acao;
drop table siafi_dbt.nc_plano_acao;
drop table siafi_dbt.nc_unificado;
drop table siafi_dbt.pf_unificado;
drop table siafi_dbt.pf_unificado_planos_acao;
drop table siafi_dbt.ted_empenhos_plano_acao;
drop table siafi_dbt.ted_resumo_orcamentario;

drop table siconv_dbt.convenio_cronograma_desembolso;
drop table siconv_dbt.convenio_desbloqueio;
drop table siconv_dbt.convenio_desembolso;
drop table siconv_dbt.convenio_empenho;
drop table siconv_dbt.convenio_historico_situacao;
drop table siconv_dbt.convenio_ingresso_contrapartida;
drop table siconv_dbt.convenio_licitacao;
drop table siconv_dbt.convenio_meta_crono_fisico;
drop table siconv_dbt.convenio_pagamento;
drop table siconv_dbt.convenio_pagamento_tributo;
drop table siconv_dbt.convenio_proposta;
drop table siconv_dbt.convenio_proposta_pagamento;
drop table siconv_dbt.convenio_prorroga_oficio;
drop table siconv_dbt.convenio_solicitacao_alteracao;
drop table siconv_dbt.convenio_solicitacao_rendimento;
drop table siconv_dbt.convenio_termo_aditivo;
drop table siconv_dbt.convenios_consolidados;
drop table siconv_dbt.emendas_convenio;
drop table siconv_dbt.meta_cronograma_desembolso;
drop table siconv_dbt.numero_transferencia;
drop table siconv_dbt.proposta_convenio;
drop table siconv_dbt.proposta_cronograma_desembolso;
drop table siconv_dbt.proposta_historico_situacao;
drop table siconv_dbt.proposta_meta_crono_fisico;
drop table siconv_dbt.resumo_convenios;
drop table siconv_dbt.resumo_termos_fomento;
drop table siconv_dbt.termo_fomento_consolidado;

commit;
```

Run: `grep -c "^drop " docs/mir-drop-legado.sql`
Expected: `41`.

- [ ] **Step 2: Simular o drop no banco local (sem apagar)**

A simulação troca o `commit` final por `rollback`. Nada é apagado.

```bash
sed 's/^commit;$/rollback;/' docs/mir-drop-legado.sql \
  | PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -v ON_ERROR_STOP=1 -q 2>&1 | tail -3
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d analytics -At -c \
  "select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where (n.nspname, c.relname) in (('siconv_dbt','resumo_convenios'),('siafi_dbt','ted_resumo_orcamentario'),
                                    ('emendas','instrumentos_emendas'),('siafi_dbt','num_transf_n_plano_acao'))"
```

Expected: o `psql` não imprime erro (termina com `ROLLBACK`, ou nada com `-q`), e a contagem é `4`, porque as tabelas continuam lá.

- [ ] **Step 3: Escrever o guia de migração do Power BI**

Criar `docs/mir-guia-migracao-power-bi.md`:

```markdown
# Migração dos painéis do MIR para os novos data marts

O dbt do MIR passou a publicar três data marts em esquema estrela, um por BI:
`mir_convenios`, `mir_teds` e `mir_emendas`. As tabelas antigas de silver e
gold listadas abaixo saíram do dbt: continuam no banco, mas **não são mais
atualizadas**. Depois de migrar os painéis, elas são removidas pelo script
`docs/mir-drop-legado.sql`.

## Como os marts funcionam

- Cada mart tem **dimensões** (`dim_*`, uma linha por coisa: convênio, plano de
  ação, emenda, parlamentar, UG, data...) e **fatos** (`fato_*`, uma linha por
  evento ou por posição, só com chaves `sk_*` e valores).
- No Power BI, relacione cada `sk_*` da fato com a dimensão de mesmo nome
  (relação um-para-muitos, filtro da dimensão para a fato). Toda dimensão tem
  a linha `-1` "Não identificado", então nenhuma chave fica vazia.
- As fatos `fato_*_posicao` têm uma linha por instrumento (ou por emenda) com
  os valores acumulados. Use-as para cartões e tabelas de resumo.
- As fatos de movimento (execução, fluxo financeiro, crédito, dotação) têm uma
  linha por evento com data (`sk_tempo`, ligada à `dim_tempo`). Use-as para
  séries no tempo.
- Restos a pagar inscritos: some `restos_a_pagar_inscritos_acumulavel`. A
  coluna `restos_a_pagar_inscritos` repete o saldo reinscrito a cada ano e só
  serve para ver o saldo de um exercício.

## Tabela antiga → onde está agora

### Convênios e termos de fomento (`siconv_dbt` → `mir_convenios`)

| Tabela antiga | Onde está agora |
|---|---|
| `resumo_convenios`, `resumo_termos_fomento` | `fato_convenio_posicao` + `dim_convenio` (a `modalidade` separa convênio e termo), `dim_convenente`, `dim_localidade` |
| `convenios_consolidados`, `termo_fomento_consolidado`, `proposta_convenio`, `convenio_proposta` | `dim_convenio`, `dim_convenente`, `dim_localidade` |
| `convenio_desembolso`, `convenio_ingresso_contrapartida`, `convenio_desbloqueio`, `convenio_pagamento`, `convenio_pagamento_tributo`, `convenio_proposta_pagamento` | `fato_fluxo_financeiro` (coluna `tipo_movimento`) + `dim_fornecedor` |
| `convenio_cronograma_desembolso`, `proposta_cronograma_desembolso`, `meta_cronograma_desembolso` | `fato_cronograma_desembolso` |
| `convenio_historico_situacao`, `proposta_historico_situacao`, `convenio_termo_aditivo`, `convenio_prorroga_oficio`, `convenio_solicitacao_alteracao`, `convenio_solicitacao_rendimento` | `fato_evento_convenio` (coluna `tipo_evento`) |
| `convenio_empenho` | empenhos do SICONV: `valor_empenhado_siconv` e `qtd_empenhos_siconv` em `fato_convenio_posicao`; execução do SIAFI por NE: `fato_execucao_orcamentaria` |
| `convenio_meta_crono_fisico`, `proposta_meta_crono_fisico`, `convenio_licitacao` | quantidades e valores em `fato_convenio_posicao` (`qtd_metas`, `qtd_licitacoes`, `valor_licitado`); `data_fim_primeira_meta` e `meta_expirada` em `dim_convenio` |
| `emendas_convenio` | `fato_execucao_orcamentaria` com `dim_emenda` e `dim_parlamentar` (NEs de emenda do convênio) |
| `numero_transferencia` | sem tabela equivalente: o vínculo NE → convênio já está em `fato_execucao_orcamentaria` (`sk_convenio`) |

### TEDs (`siafi_dbt` → `mir_teds`)

| Tabela antiga | Onde está agora |
|---|---|
| `ted_resumo_orcamentario` | `fato_plano_acao_posicao` + `dim_plano_acao` |
| `ted_empenhos_plano_acao`, `empenhos_por_plano_acao` | `fato_execucao_orcamentaria` |
| `nc_plano_acao`, `nc_unificado` | `fato_credito_descentralizado` |
| `pf_unificado`, `pf_unificado_planos_acao` | `fato_programacao_financeira` |
| `num_transf_n_plano_acao` (view) | coluna `num_transf` de `dim_plano_acao` |

### Emendas (`emendas` → `mir_emendas`)

| Tabela antiga | Onde está agora |
|---|---|
| `resumo_emendas_orcamento_execucao`, `emendas_orcamento_execucao` | `fato_emenda_posicao` (uma linha por emenda); por data: `fato_execucao_orcamentaria` e `fato_dotacao` |
| `emendas_partidos` | `dim_parlamentar` (uma linha por parlamentar × cargo × partido, com `valido_de`/`valido_ate`); a fato já traz o partido da data da NE |
| `instrumentos_emendas`, `emendas_instrumentos_execucao` | `dim_instrumento_executor` + `fato_execucao_orcamentaria` |
| `emendas_execucao_por_ug` | `fato_execucao_orcamentaria` + `dim_unidade_gestora` |

`emendas.planos_partidos` (planos de ação das transferências especiais) **não
muda**.

## Números que mudam de propósito

- **Convênios:** `resumo_convenios` tinha convênios repetidos (834 linhas para
  643 convênios). Somas feitas direto nela ficavam de 32% a 52% acima do real.
  Os marts têm um convênio por linha, então os totais novos são menores.
- **Restos a pagar inscritos:** a soma antiga contava a reinscrição do mesmo
  saldo a cada ano. O acumulado novo não conta (R$ 12,2 mi a menos no dump).
- **Origem do recurso:** vem das notas de empenho. Instrumentos com NE de
  emenda são "Emenda" mesmo sem parlamentar registrado no SICONV.
- **TEDs:** o vínculo das NEs, NCs e PFs com o plano cobre casos que o modelo
  antigo perdia e não conta mais as NCs internas do MIR (238012 → 810008).
- **Indicador I1** (`indicadores.i1_*`): passa a ler os marts. Na saída
  `i1_ted_por_instrumento`, a coluna `n_linhas_resumo` virou `qtd_nes`
  (quantidade de NEs do plano).

## Ordem sugerida

1. Para cada painel, listar as tabelas antigas que ele lê (Power Query →
   Fonte) e trocar pelas do mart, conforme as tabelas acima.
2. Conferir os totais do painel com os números que mudam de propósito.
3. Quando nenhum painel ler mais as tabelas antigas, rodar
   `docs/mir-drop-legado.sql`. Se algum objeto ainda depender delas, o script
   falha sem apagar nada.
```

- [ ] **Step 4: Atualizar o spec**

Em `docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md`:

1. §9: substituir o primeiro item (`dags/indicadores/mir/i1_valor_executado_dag.py`: ...) por:

```markdown
- `dags/indicadores/mir/i1_valor_executado_dag.py`: o `FONTES` lê `mir_teds.dim_plano_acao`, `fato_plano_acao_posicao`, `fato_execucao_orcamentaria` e `dim_acao_orcamentaria`, e `mir_convenios.dim_convenio`, `fato_convenio_posicao`, `dim_convenente` e `dim_localidade`. A etapa da cadeia usa as quantidades de PF, NC e NE da posição do plano; o programa de governo do TED é o de maior empenhado nas NEs do plano. Na saída `i1_ted_por_instrumento`, `n_linhas_resumo` virou `qtd_nes` (decisão do usuário em 2026-09-29).
```

2. §10: substituir a lista por:

```markdown
- `siconv_dbt/silver/*` (25 modelos) e `siconv_dbt/gold/*` (2);
- `empenhos_ted_dbt/silver/*` (5), `empenhos_ted_dbt/views/*` (1) e `empenhos_ted_dbt/gold/*` (2);
- `emendas_dbt/gold/*` (3) e, de `emendas_dbt/silver/`, `emendas_orcamento_execucao`, `emendas_partidos` e `instrumentos_emendas`. O `planos_partidos` (transferências especiais, fora do escopo pelo §1) fica;
- os blocos correspondentes em `schema.yml`, as análises de paridade e os testes dos modelos antigos.

As tabelas órfãs não são apagadas pelo dbt: o usuário roda `docs/mir-drop-legado.sql` (41 objetos, sem `cascade`) em produção depois de migrar os painéis (decisão do usuário em 2026-09-29). O guia para a equipe dos painéis está em `docs/mir-guia-migracao-power-bi.md`.
```

(a linha seguinte, "A bronze desses domínios e ... permanecem.", fica.)

3. §12, item 5: acrescentar ao fim `O dbt_project.yml não precisou mudar: os blocos dos domínios antigos continuam configurando a bronze.`

4. §13, item "Painéis Power BI existentes": substituir por `- **Painéis Power BI existentes** que leem os golds antigos continuam abrindo depois do deploy, com dados parados, até a migração; o guia \`docs/mir-guia-migracao-power-bi.md\` mapeia cada tabela antiga para o mart. O script de \`drop\` falha sem apagar nada se algum objeto ainda depender das tabelas.`

- [ ] **Step 5: Verificação final**

```bash
cd /home/joaoegewarth/data-application-mir
python3 -m pytest tests/test_plugins/test_indicadores_i1.py -q -p no:cacheprovider 2>&1 | grep -E "passed|failed"
git status --short -- airflow_lappis docs .claude tests
git diff --cached --name-only | grep -vc '^dicionario-mir/'
```

Expected: `29 passed`; o `git status` mostra só os três arquivos desta tarefa (`?? docs/mir-drop-legado.sql`, `?? docs/mir-guia-migracao-power-bi.md`, ` M docs/superpowers/specs/...`); o último comando imprime `0`.

- [ ] **Step 6: Commit**

```bash
git add -- docs/mir-drop-legado.sql docs/mir-guia-migracao-power-bi.md docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md
git commit -m "docs(dbt/mir): script de drop do legado e guia de migracao do Power BI" \
  -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" \
  -- docs/mir-drop-legado.sql docs/mir-guia-migracao-power-bi.md docs/superpowers/specs/2026-09-29-remodelagem-fato-dimensao-design.md
```

## Fora desta etapa

- Rodar `docs/mir-drop-legado.sql` em produção (o usuário, depois de migrar os painéis).
- Squash dos trailers `Co-Authored-By` errados da etapa 1 (f15a6a0, 67875d4, 65f0015), antes do PR.
- Descrição do PR: diferenças da paridade das etapas 2 a 5 e a lista de valores do I1 que mudaram.
