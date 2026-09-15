"""Testes do indicador I9 — Municípios Atendidos (Convênios/Fomentos).

Cada teste unitário cobre uma decisão metodológica registrada no script
original da equipe de BI (i9_municipios_atendidos_convenios.py). Os testes
de regressão usam os CSVs entregues pelo BI em `tests/fixtures` como saída
esperada — igual ao I1/I2, este indicador foi validado ponta-a-ponta.

O cadastro `TOTAL_MUNICIPIOS_POR_UF` foi buscado e cruzado contra fontes
públicas (não inventado) — ver docstring do módulo para a checagem cruzada
de Pernambuco e Mato Grosso, e a correção do DF feita a partir da própria
regressão contra o dado real da BI.
"""

import csv
from pathlib import Path

import pytest

from indicadores.i9_municipios_atendidos import (
    TOTAL_MUNICIPIOS_BRASIL,
    TOTAL_MUNICIPIOS_POR_UF,
    calcular_cobertura_nacional,
    calcular_cobertura_uf,
    calcular_i9,
)

FIXTURES_I9 = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i9"
FIXTURES_I1 = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _municipio(municipio, uf, n_instrumentos=1, **extra):
    base = {
        "municipio_execucao": municipio,
        "uf_execucao": uf,
        "n_instrumentos": n_instrumentos,
    }
    base.update(extra)
    return base


def _ler_fixture(pasta, nome):
    with open(pasta / nome, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Cadastro de referência
# ---------------------------------------------------------------------------
def test_soma_dos_26_estados_bate_com_total_nacional() -> None:
    """Critério de aceite da tabela: bate exatamente com o valor da BI."""
    sem_df = {uf: n for uf, n in TOTAL_MUNICIPIOS_POR_UF.items() if uf != "DF"}
    assert sum(sem_df.values()) == TOTAL_MUNICIPIOS_BRASIL


def test_df_conta_como_1_municipio_estatistico() -> None:
    """Brasília — decisão corrigida por regressão contra o dado real da BI."""
    assert TOTAL_MUNICIPIOS_POR_UF["DF"] == 1


# ---------------------------------------------------------------------------
# Cobertura nacional
# ---------------------------------------------------------------------------
def test_nao_informado_fica_fora_da_contagem() -> None:
    municipios = [
        _municipio("BRASÍLIA", "DF"),
        _municipio("NAO_INFORMADO", "NAO_INFORMADO"),
    ]

    [nacional] = calcular_cobertura_nacional(municipios)

    assert nacional["municipios_atendidos"] == 1


def test_cobertura_nacional_percentual_sobre_5570() -> None:
    municipios = [_municipio(f"MUN{i}", "SP") for i in range(10)]

    [nacional] = calcular_cobertura_nacional(municipios)

    assert nacional["cobertura_pct"] == round(10 / 5570 * 100, 2)


def test_cobertura_nacional_soma_n_instrumentos() -> None:
    municipios = [
        _municipio("A", "SP", n_instrumentos=3),
        _municipio("B", "SP", n_instrumentos=2),
    ]

    [nacional] = calcular_cobertura_nacional(municipios)

    assert nacional["n_instrumentos"] == 5


# ---------------------------------------------------------------------------
# Cobertura por UF
# ---------------------------------------------------------------------------
def test_cobertura_uf_usa_total_do_cadastro() -> None:
    municipios = [_municipio("Cuiabá", "MT")]

    [uf] = calcular_cobertura_uf(municipios)

    assert uf["total_municipios_uf"] == 142
    assert uf["cobertura_pct"] == round(1 / 142 * 100, 2)


def test_cobertura_uf_vazia_quando_total_uf_ausente() -> None:
    """UF fora do cadastro (não deveria acontecer, mas não quebra)."""
    municipios = [_municipio("X", "ZZ")]

    [uf] = calcular_cobertura_uf(municipios)

    assert uf["total_municipios_uf"] == 0
    assert uf["cobertura_pct"] == ""


def test_cobertura_uf_ordenada_por_municipios_atendidos_desc() -> None:
    municipios = [
        _municipio("A", "SP"), _municipio("B", "SP"),
        _municipio("C", "RJ"),
    ]

    ufs = calcular_cobertura_uf(municipios)

    assert [u["uf"] for u in ufs] == ["SP", "RJ"]


# ---------------------------------------------------------------------------
# Regressão — contra os resultados entregues pelo BI
# ---------------------------------------------------------------------------
def test_regressao_cobertura_nacional() -> None:
    municipios_i1 = _ler_fixture(FIXTURES_I1, "i1_convenios_por_municipio.csv")
    [esperado] = _ler_fixture(FIXTURES_I9, "i9_convenio_cobertura_nacional.csv")

    [obtido] = calcular_cobertura_nacional(municipios_i1)

    assert obtido["municipios_atendidos"] == int(esperado["municipios_atendidos"])
    assert obtido["total_municipios_brasil"] == int(esperado["total_municipios_brasil"])
    assert obtido["cobertura_pct"] == pytest.approx(
        float(esperado["cobertura_pct"]), abs=0.011
    )
    assert obtido["n_instrumentos"] == int(esperado["n_instrumentos"])


def test_regressao_cobertura_uf() -> None:
    municipios_i1 = _ler_fixture(FIXTURES_I1, "i1_convenios_por_municipio.csv")
    esperado = _ler_fixture(FIXTURES_I9, "i9_convenio_cobertura_uf.csv")

    obtido = calcular_cobertura_uf(municipios_i1)

    assert len(obtido) == len(esperado)
    for o, e in zip(obtido, esperado):
        assert o["uf"] == e["uf"]
        assert o["municipios_atendidos"] == int(e["municipios_atendidos"])
        assert o["total_municipios_uf"] == int(e["total_municipios_uf"])
        assert o["n_instrumentos"] == int(e["n_instrumentos"])
        if e["cobertura_pct"] == "":
            assert o["cobertura_pct"] == ""
        else:
            assert o["cobertura_pct"] == pytest.approx(
                float(e["cobertura_pct"]), abs=0.011
            )


def test_calcular_i9_devolve_as_duas_saidas() -> None:
    saidas = calcular_i9([_municipio("Cuiabá", "MT")])

    assert set(saidas) == {"i9_convenio_cobertura_nacional", "i9_convenio_cobertura_uf"}
    assert len(saidas["i9_convenio_cobertura_nacional"]) == 1
    assert len(saidas["i9_convenio_cobertura_uf"]) == 1
