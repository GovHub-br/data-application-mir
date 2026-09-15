"""Testes do indicador I7 — Completude e Qualidade dos Dados.

Cada teste unitário cobre uma decisão metodológica registrada no script
original da equipe de BI (i7_completude.py).

AVISO: ao contrário do I1/I2, não há fixture de regressão contra os CSVs
que a BI publicou (`i7_completude_*_ted.csv`, `i7_completude_*_convenios.csv`)
— aquele resultado veio de um export específico do OneDrive, com colunas e
cardinalidade diferentes das tabelas bronze do dbt que este módulo lê. Os
testes aqui usam dados sintéticos para cobrir o critério de ausência, as
faixas e a heurística de tipo de ausência.
"""

from datetime import date
from decimal import Decimal

from indicadores.i7_completude import calcular_i7, completude_tabela, consolidar_i7

# ---------------------------------------------------------------------------
# Critério de ausência
# ---------------------------------------------------------------------------
def test_valor_vazio_e_none_sao_ausentes() -> None:
    linhas = [{"a": None}, {"a": ""}, {"a": "   "}]

    cols, _ = completude_tabela("TEDs", "tab", linhas)

    assert cols[0]["n_ausentes"] == 3


def test_marcadores_de_ausencia_dos_sistemas_de_origem() -> None:
    linhas = [
        {"a": "SEM INFORMACAO"}, {"a": "sem informação"}, {"a": "-8"}, {"a": "-9"},
    ]

    cols, _ = completude_tabela("TEDs", "tab", linhas)

    assert cols[0]["n_ausentes"] == 4


def test_zero_e_flags_texto_sao_preenchidos_nao_ausentes() -> None:
    linhas = [{"a": 0}, {"a": "NAO"}, {"a": "SIM"}]

    cols, _ = completude_tabela("TEDs", "tab", linhas)

    assert cols[0]["n_ausentes"] == 0


def test_aceita_tipos_tipados_do_postgres_sem_erro() -> None:
    """Coluna vem tipada (Decimal/date/int), não texto — precisa normalizar antes."""
    linhas = [
        {"valor": Decimal("100.50"), "dt": date(2024, 1, 1), "n": 5},
        {"valor": None, "dt": None, "n": 0},
    ]

    cols, _ = completude_tabela("TEDs", "tab", linhas)
    por_coluna = {c["coluna"]: c for c in cols}

    assert por_coluna["valor"]["n_ausentes"] == 1
    assert por_coluna["dt"]["n_ausentes"] == 1
    assert por_coluna["n"]["n_ausentes"] == 0  # 0 é preenchido, não ausente


# ---------------------------------------------------------------------------
# Faixas
# ---------------------------------------------------------------------------
def test_faixa_ok_abaixo_de_10_por_cento_ausente() -> None:
    linhas = [{"a": "x"}] * 9 + [{"a": None}]  # 10% ausente -> não é <10%

    [col] = completude_tabela("TEDs", "tab", linhas)[0]
    assert col["faixa"] == "ATENCAO"


def test_faixa_atencao_entre_10_e_50_por_cento() -> None:
    linhas = [{"a": "x"}] * 7 + [{"a": None}] * 3  # 30% ausente

    [col] = completude_tabela("TEDs", "tab", linhas)[0]
    assert col["faixa"] == "ATENCAO"


def test_faixa_critico_acima_de_50_por_cento() -> None:
    linhas = [{"a": "x"}] * 4 + [{"a": None}] * 6  # 60% ausente

    [col] = completude_tabela("TEDs", "tab", linhas)[0]
    assert col["faixa"] == "CRITICO"


def test_faixa_ok_sem_nenhuma_ausencia() -> None:
    linhas = [{"a": "x"}] * 10

    [col] = completude_tabela("TEDs", "tab", linhas)[0]
    assert col["faixa"] == "OK"
    assert col["pct_ausente"] == 0.0


# ---------------------------------------------------------------------------
# Heurística de tipo de ausência (sugestão, não classificação curada)
# ---------------------------------------------------------------------------
def test_coluna_sem_ausencia_e_completo() -> None:
    linhas = [{"a": "x"}, {"a": "y"}]

    [col] = completude_tabela("TEDs", "tab", linhas)[0]
    assert col["tipo_ausencia_sugerido"] == "completo"


def test_coluna_100_por_cento_ausente_e_estrutural_suspeita() -> None:
    linhas = [{"a": None}, {"a": None}]

    [col] = completude_tabela("TEDs", "tab", linhas)[0]
    assert col["tipo_ausencia_sugerido"] == "estrutural_suspeita"


def test_coluna_parcialmente_ausente_e_dado_faltante() -> None:
    linhas = [{"a": "x"}, {"a": None}]

    [col] = completude_tabela("TEDs", "tab", linhas)[0]
    assert col["tipo_ausencia_sugerido"] == "dado_faltante"


# ---------------------------------------------------------------------------
# Resumo por tabela
# ---------------------------------------------------------------------------
def test_resumo_tabela_conta_colunas_criticas_e_estruturais() -> None:
    linhas = [
        {"critica": None, "estrutural": None, "ok": "x"},
        {"critica": None, "estrutural": None, "ok": "y"},
        {"critica": "z", "estrutural": None, "ok": "w"},
    ]
    # critica: 2/3 = 66,7% ausente (>50%, crítica mas não estrutural)
    # estrutural: 3/3 = 100% ausente (estrutural)
    # ok: 0% ausente

    _, resumo = completude_tabela("TEDs", "tab", linhas)

    assert resumo["n_registros"] == 3
    assert resumo["n_colunas"] == 3
    assert resumo["n_colunas_criticas"] == 2  # critica E estrutural passam de 50%
    assert resumo["n_colunas_estruturais_suspeitas"] == 1


def test_tabela_vazia_nao_gera_linhas() -> None:
    cols, resumo = completude_tabela("TEDs", "tab_vazia", [])

    assert cols == []
    assert resumo is None


# ---------------------------------------------------------------------------
# Orquestração — filtros por pasta e ordenação
# ---------------------------------------------------------------------------
def test_calcular_i7_devolve_as_seis_saidas() -> None:
    tabelas = {
        "TEDs": {"planos_acao_ted": [{"a": None}, {"a": "x"}]},
        "Convênios": {"convenio": [{"b": "x"}]},
        "Emendas": {"tg_emendas": [{"c": "x"}]},
    }

    saidas = calcular_i7(tabelas)

    assert set(saidas) == {
        "i7_completude_colunas",
        "i7_completude_arquivos",
        "i7_completude_colunas_ted",
        "i7_completude_arquivos_ted",
        "i7_completude_colunas_convenios",
        "i7_completude_arquivos_convenios",
    }


def test_consolidar_i7_processa_tabela_por_vez_sem_acumular_linhas_brutas() -> None:
    """Mesmo fluxo que a DAG usa: completude_tabela chamada uma vez por
    tabela (descartando as linhas brutas em seguida), só os resultados
    agregados chegam em consolidar_i7."""
    linhas_colunas: list[dict] = []
    linhas_tabelas: list[dict] = []
    for pasta, nome, linhas in [
        ("TEDs", "planos_acao_ted", [{"a": "x"}, {"a": None}]),
        ("Convênios", "convenio", [{"b": "x"}]),
    ]:
        cols, resumo = completude_tabela(pasta, nome, linhas)
        linhas_colunas.extend(cols)
        linhas_tabelas.append(resumo)

    saidas = consolidar_i7(linhas_colunas, linhas_tabelas)

    assert {l["arquivo"] for l in saidas["i7_completude_arquivos_ted"]} == {
        "planos_acao_ted"
    }
    assert {l["arquivo"] for l in saidas["i7_completude_arquivos_convenios"]} == {
        "convenio"
    }


def test_calcular_i7_filtra_saidas_ted_e_convenios_por_pasta() -> None:
    tabelas = {
        "TEDs": {"planos_acao_ted": [{"a": "x"}]},
        "Convênios": {"convenio": [{"b": "x"}]},
        "Emendas": {"tg_emendas": [{"c": "x"}]},
    }

    saidas = calcular_i7(tabelas)

    assert {l["arquivo"] for l in saidas["i7_completude_arquivos_ted"]} == {
        "planos_acao_ted"
    }
    assert {l["arquivo"] for l in saidas["i7_completude_arquivos_convenios"]} == {
        "convenio"
    }
    # Emendas não tem saída filtrada própria (decisão herdada do script original),
    # mas aparece na saída completa.
    assert any(l["pasta"] == "Emendas" for l in saidas["i7_completude_arquivos"])


def test_calcular_i7_ordena_colunas_da_pior_para_a_melhor() -> None:
    tabelas = {
        "TEDs": {
            "tab_a": [{"x": "preenchido"}, {"x": "preenchido"}],  # 0% ausente
            "tab_b": [{"y": None}, {"y": None}],  # 100% ausente
        },
    }

    saidas = calcular_i7(tabelas)
    percentuais = [l["pct_ausente"] for l in saidas["i7_completude_colunas"]]

    assert percentuais == sorted(percentuais, reverse=True)


def test_calcular_i7_ignora_tabelas_vazias() -> None:
    tabelas = {"TEDs": {"tab_vazia": []}}

    saidas = calcular_i7(tabelas)

    assert saidas["i7_completude_colunas"] == []
    assert saidas["i7_completude_arquivos"] == []
