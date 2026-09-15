"""Testes do indicador I2 — Concentração Institucional dos Executores.

Cada teste unitário cobre uma decisão metodológica registrada no script
original da equipe de BI (i2_concentracao_executores.py /
i2_concentracao_executores_convenios.py). Os testes de regressão usam os
CSVs entregues pelo BI em `tests/fixtures` como saída esperada.
"""

import csv
from pathlib import Path

import pytest

from indicadores.i2_concentracao_executores import (
    agregar_convenio_por_executor,
    agregar_ted_por_executor,
    calcular_convenio_localizacao_institucional,
    calcular_i2,
    calcular_resumo_convenio,
    calcular_resumo_ted,
    calcular_ted_localizacao_institucional,
)

FIXTURES_I2 = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i2"
FIXTURES_I1 = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ted_i1(
    id_plano_acao, sigla="UFX", nome="Universidade X", vl_firmado=1000.0, **extra
):
    base = {
        "id_plano_acao": id_plano_acao,
        "sigla_executor": sigla,
        "nome_executor": nome,
        "programa_governo": "5804",
        "origem": "orcamento_regular",
        "ano": "2024",
        "vl_firmado": vl_firmado,
    }
    base.update(extra)
    return base


def _convenio_i1(
    nr_convenio, convenente="Prefeitura X", uf="DF", empenhado=1000.0, **extra
):
    base = {
        "nr_convenio": nr_convenio,
        "convenente": convenente,
        "categoria_convenente": "Administração Pública Municipal",
        "uf_execucao": uf,
        "municipio_execucao": "BRASÍLIA",
        "instrumento": "CONVENIO",
        "origem": "orcamento_regular",
        "ano": 2024,
        "empenhado_liquido": empenhado,
    }
    base.update(extra)
    return base


def _ler_fixture(pasta, nome, numericos=(), inteiros=()):
    with open(pasta / nome, encoding="utf-8-sig") as f:
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
# Bloco 1 — TED: UF-sede e tipo institucional
# ---------------------------------------------------------------------------
def test_ted_uf_sede_vem_do_dicionario_por_sigla() -> None:
    """Decisão 1: leitura institucional (sede), não territorial."""
    [ted] = calcular_ted_localizacao_institucional([_ted_i1(1, sigla="UFPR")])

    assert ted["uf_sede"] == "PR"
    assert ted["tipo_institucional"] == "Universidade Federal"


def test_ted_sigla_nao_mapeada_fica_explicita() -> None:
    [ted] = calcular_ted_localizacao_institucional([_ted_i1(1, sigla="XPTO")])

    assert ted["uf_sede"] == "NAO_MAPEADO"
    assert ted["tipo_institucional"] == "Outro"


def test_ted_sigla_vazia_corrigida_pelo_nome_conhecido() -> None:
    """Decisão 4: sigla vazia é inferida pelo nome do executor quando possível."""
    [ted] = calcular_ted_localizacao_institucional(
        [_ted_i1(1, sigla="", nome="Universidade Federal do Parana")]
    )

    assert ted["sigla_executor"] == "UFPR"
    assert ted["uf_sede"] == "PR"


def test_ted_sigla_vazia_sem_nome_conhecido_vira_sem_sigla() -> None:
    [ted] = calcular_ted_localizacao_institucional(
        [_ted_i1(1, sigla="", nome="Orgao Qualquer")]
    )

    assert ted["sigla_executor"] == "SEM_SIGLA"


def test_ted_tipo_institucional_por_correspondencia_exata_nao_prefixo() -> None:
    """Decisão 3: UNIFEI não é confundida com universidade 'UF*' por prefixo."""
    [unifei] = calcular_ted_localizacao_institucional([_ted_i1(1, sigla="UNIFEI")])
    [instituto] = calcular_ted_localizacao_institucional([_ted_i1(2, sigla="IFBA")])
    [outro] = calcular_ted_localizacao_institucional([_ted_i1(3, sigla="IPEA")])

    assert unifei["tipo_institucional"] == "Universidade Federal"
    assert instituto["tipo_institucional"] == "Instituto Federal"
    assert outro["tipo_institucional"] == "Outro"


# ---------------------------------------------------------------------------
# Bloco 1 — TED: agregação e HHI
# ---------------------------------------------------------------------------
def test_ted_hhi_calculado_sobre_vl_firmado() -> None:
    """Decisão 2: base do HHI é vl_firmado, não empenhado (não existe no I2)."""
    loc = calcular_ted_localizacao_institucional([
        _ted_i1(1, sigla="A", vl_firmado=600.0),
        _ted_i1(2, sigla="A", vl_firmado=0.0),
        _ted_i1(3, sigla="B", vl_firmado=400.0),
    ])

    [resumo] = calcular_resumo_ted(loc)

    # A: 60% -> 3600; B: 40% -> 1600; HHI = 5200
    assert resumo["hhi"] == 5200.0
    assert resumo["n_executores_distintos"] == 2
    assert resumo["total_firmado"] == 1000.0


def test_ted_concentracao_agrupa_por_sigla_e_ordena_desc() -> None:
    loc = calcular_ted_localizacao_institucional([
        _ted_i1(1, sigla="A", vl_firmado=100.0),
        _ted_i1(2, sigla="B", vl_firmado=900.0),
        _ted_i1(3, sigla="A", vl_firmado=100.0),
    ])

    conc = agregar_ted_por_executor(loc)

    assert [c["sigla_executor"] for c in conc] == ["B", "A"]
    assert conc[0]["n_teds"] == 1
    assert conc[1]["n_teds"] == 2
    assert conc[1]["vl_firmado"] == 200.0
    assert conc[0]["share_pct"] == pytest.approx(81.82, abs=0.01)  # 900 / 1100


# ---------------------------------------------------------------------------
# Bloco 2 — Convênios: recorte de campos e agregação
# ---------------------------------------------------------------------------
def test_convenio_localizacao_recorta_campos_do_universo_do_i1() -> None:
    [conv] = calcular_convenio_localizacao_institucional([_convenio_i1(1)])

    assert set(conv) == {
        "nr_convenio", "convenente", "categoria_convenente", "uf_execucao",
        "municipio_execucao", "instrumento", "origem", "ano", "empenhado_liquido",
    }


def test_convenio_hhi_calculado_sobre_empenhado_liquido() -> None:
    """Decisão 2: base do HHI para convênios é empenhado_liquido, não vl_firmado."""
    loc = calcular_convenio_localizacao_institucional([
        _convenio_i1(1, convenente="X", empenhado=750.0),
        _convenio_i1(2, convenente="Y", empenhado=250.0),
    ])

    [resumo] = calcular_resumo_convenio(loc)

    # X: 75% -> 5625; Y: 25% -> 625; HHI = 6250
    assert resumo["hhi"] == 6250.0
    assert resumo["n_convenentes_distintos"] == 2


def test_convenio_agrega_por_nome_do_convenente_sem_cnpj() -> None:
    """Decisão 5: sem CNPJ disponível, agregação é por nome (risco de grafia)."""
    loc = calcular_convenio_localizacao_institucional([
        _convenio_i1(1, convenente="Prefeitura de X"),
        _convenio_i1(2, convenente="Prefeitura de X"),
    ])

    [conc] = agregar_convenio_por_executor(loc)

    assert conc["n_instrumentos"] == 2


def test_convenio_reporta_n_ufs_distintas_em_vez_de_uf_unica() -> None:
    """Decisão 6: um convenente pode executar em mais de uma UF."""
    loc = calcular_convenio_localizacao_institucional([
        _convenio_i1(1, convenente="X", uf="DF"),
        _convenio_i1(2, convenente="X", uf="GO"),
        _convenio_i1(3, convenente="X", uf="DF"),
    ])

    [conc] = agregar_convenio_por_executor(loc)

    assert conc["n_ufs_distintas"] == 2
    assert "uf_execucao" not in conc
    assert "uf_sede" not in conc


# ---------------------------------------------------------------------------
# Regressão — contra os resultados entregues pelo BI
# ---------------------------------------------------------------------------
def test_regressao_ted_localizacao_institucional() -> None:
    teds_i1 = _ler_fixture(FIXTURES_I1, "i1_ted_por_instrumento.csv")
    esperado = _ler_fixture(FIXTURES_I2, "i2_ted_localizacao_institucional.csv",
                             numericos=("vl_firmado",))

    _assert_linhas_iguais(calcular_ted_localizacao_institucional(teds_i1), esperado)


def test_regressao_ted_concentracao() -> None:
    teds_i1 = _ler_fixture(FIXTURES_I1, "i1_ted_por_instrumento.csv")
    esperado = _ler_fixture(
        FIXTURES_I2, "i2_executores_concentracao.csv",
        numericos=("vl_firmado", "share_pct", "share_pct_ao_quadrado"),
        inteiros=("n_teds",),
    )

    loc = calcular_ted_localizacao_institucional(teds_i1)
    _assert_linhas_iguais(agregar_ted_por_executor(loc), esperado)


def test_regressao_ted_resumo() -> None:
    teds_i1 = _ler_fixture(FIXTURES_I1, "i1_ted_por_instrumento.csv")
    esperado = _ler_fixture(
        FIXTURES_I2, "i2_resumo.csv",
        numericos=("total_firmado", "hhi"),
        inteiros=("n_teds", "n_executores_distintos"),
    )

    loc = calcular_ted_localizacao_institucional(teds_i1)
    _assert_linhas_iguais(calcular_resumo_ted(loc), esperado)


def test_regressao_convenio_localizacao_institucional() -> None:
    convenios_i1 = _ler_fixture(FIXTURES_I1, "i1_convenios_por_instrumento.csv")
    esperado = _ler_fixture(FIXTURES_I2, "i2_convenio_localizacao_institucional.csv",
                             numericos=("empenhado_liquido",))

    obtido = calcular_convenio_localizacao_institucional(convenios_i1)
    _assert_linhas_iguais(obtido, esperado)


def test_regressao_convenio_concentracao() -> None:
    convenios_i1 = _ler_fixture(FIXTURES_I1, "i1_convenios_por_instrumento.csv")
    esperado = _ler_fixture(
        FIXTURES_I2, "i2_convenio_concentracao.csv",
        numericos=("empenhado_liquido", "share_pct", "share_pct_ao_quadrado"),
        inteiros=("n_instrumentos", "n_ufs_distintas"),
    )

    loc = calcular_convenio_localizacao_institucional(convenios_i1)
    _assert_linhas_iguais(agregar_convenio_por_executor(loc), esperado)


def test_regressao_convenio_resumo() -> None:
    convenios_i1 = _ler_fixture(FIXTURES_I1, "i1_convenios_por_instrumento.csv")
    esperado = _ler_fixture(
        FIXTURES_I2, "i2_resumo_convenio.csv",
        numericos=("total_empenhado", "hhi"),
        inteiros=("n_instrumentos", "n_convenentes_distintos"),
    )

    loc = calcular_convenio_localizacao_institucional(convenios_i1)
    _assert_linhas_iguais(calcular_resumo_convenio(loc), esperado)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i2_devolve_as_seis_saidas() -> None:
    saidas = calcular_i2(
        teds_i1=[_ted_i1(1)],
        convenios_i1=[_convenio_i1(1)],
    )

    assert set(saidas) == {
        "i2_ted_localizacao_institucional",
        "i2_executores_concentracao",
        "i2_resumo",
        "i2_convenio_localizacao_institucional",
        "i2_convenio_concentracao",
        "i2_resumo_convenio",
    }
    assert saidas["i2_resumo"][0]["n_teds"] == 1
    assert saidas["i2_resumo_convenio"][0]["n_instrumentos"] == 1
