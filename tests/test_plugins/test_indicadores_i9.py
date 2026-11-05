"""Testes do indicador I9 — Municípios Atendidos (Convênios/Fomentos).

O I9 lia ``indicadores.i1_convenios_por_municipio``, saída do I1 antigo que
deixou de existir quando o I1 passou para o Bloco 1 (o território foi para o
I1b). Agora ele lê as mesmas fontes dbt do I1b e aplica a mesma regra de
território do I1b, só que no grão de município. Os testes cobrem:

- o universo, que é o do I1 Convênios (Bloco 1);
- a fonte do município: meta física primeiro e, sem meta, o município da gold
  (mesma ordem da UF do I1b);
- a fórmula de cobertura, por regressão contra os CSVs da BI.

O cadastro ``TOTAL_MUNICIPIOS_POR_UF`` foi buscado e cruzado contra fontes
públicas (não inventado). A docstring do módulo registra a checagem cruzada de
Pernambuco e Mato Grosso e a correção do DF, feita a partir da própria
regressão contra o dado real da BI.
"""

import csv
from pathlib import Path

import pytest

from indicadores.i1_valor_executado import calcular_i1_convenios
from indicadores.i1b_convenios_uf_ano import (
    montar_instrumentos as montar_instrumentos_i1b,
)
from indicadores.i9_municipios_atendidos import (
    TOTAL_MUNICIPIOS_BRASIL,
    TOTAL_MUNICIPIOS_POR_UF,
    calcular_cobertura_nacional,
    calcular_cobertura_uf,
    calcular_i9,
    localizar_municipios,
)

FIXTURES_I9 = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i9"
FIXTURES_I1 = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _convenio(nr, **extra):
    """Linha de resumo_convenios dentro do universo do I1, salvo override."""
    base = {
        "nr_convenio": nr,
        "modalidade_instrumento": "CONVENIO",
        "situacao_atual": "Em execução",
        "data_assinatura": "2024-03-01",
        "inicio_vigencia": "2024-03-01",
        "valor_firmado_atualizado": 100.0,
        "valor_empenhado": 100.0,
        "valor_total_pago": 50.0,
        "parlamentares": None,
        "uf_execucao": None,
        "municipio_execucao": None,
    }
    base.update(extra)
    return base


def _meta(nr, municipio, uf):
    return {"nr_convenio": nr, "municipio_meta": municipio, "uf_meta": uf}


def _local(nr, municipio, uf):
    return {"nr_convenio": nr, "municipio": municipio, "uf": uf}


def _ler_fixture(pasta, nome):
    with open(pasta / nome, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _localizacoes_da_fixture_i1():
    """Expande ``i1_convenios_por_municipio`` (grão município) em instrumentos.

    A fixture da BI só traz ``n_instrumentos`` por município. Cada município
    vira ``n_instrumentos`` instrumentos sintéticos, um por linha, que é o
    grão de entrada da fórmula de cobertura.
    """
    localizacoes = []
    for linha in _ler_fixture(FIXTURES_I1, "i1_convenios_por_municipio.csv"):
        municipio, uf = linha["municipio_execucao"], linha["uf_execucao"]
        for k in range(int(linha["n_instrumentos"])):
            localizacoes.append(_local(f"{municipio}/{uf}/{k}", municipio, uf))
    return localizacoes


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
# Universo — o mesmo do I1 Convênios (Bloco 1)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fora_do_universo",
    [
        {"data_assinatura": "2022-12-31", "inicio_vigencia": "2022-12-31"},
        {"situacao_atual": "Cancelado"},
        {"situacao_atual": "Convênio Anulado"},
        {"valor_empenhado": 0.0, "valor_total_pago": 10.0},
    ],
    ids=["antes_de_2023", "cancelado", "anulado", "empenho_zero_com_pagamento"],
)
def test_instrumento_fora_do_universo_do_i1_nao_conta(fora_do_universo) -> None:
    gold = [_convenio("1"), _convenio("2", **fora_do_universo)]
    metas = [_meta("1", "RECIFE", "PE"), _meta("2", "OLINDA", "PE")]

    localizacoes = localizar_municipios(gold, metas)

    assert {loc["nr_convenio"] for loc in localizacoes} == {"1"}


def test_universo_e_identico_ao_do_i1_convenios() -> None:
    gold = [
        _convenio("1"),
        _convenio("2", data_assinatura=None, inicio_vigencia="2023-05-01"),
        _convenio("3", data_assinatura="2021-01-01"),
        _convenio("4", situacao_atual="Cancelado"),
        _convenio("5", valor_empenhado=0.0, valor_total_pago=1.0),
        _convenio("6", valor_empenhado=0.0, valor_total_pago=0.0),
    ]
    metas = [_meta(str(n), f"MUNICIPIO {n}", "BA") for n in range(1, 7)]

    localizacoes = localizar_municipios(gold, metas)
    universo_i1 = {
        i["nr_convenio"] for i in calcular_i1_convenios(gold)["i1_convenio_instrumentos"]
    }

    assert {loc["nr_convenio"] for loc in localizacoes} == universo_i1 == {"1", "2", "6"}


def test_universo_vazio_falha() -> None:
    with pytest.raises(ValueError, match="Universo vazio"):
        calcular_i9([_convenio("1", situacao_atual="Cancelado")], [])


# ---------------------------------------------------------------------------
# Fonte do município — mesma ordem da UF do I1b
# ---------------------------------------------------------------------------
def test_municipio_vem_da_meta_fisica() -> None:
    localizacoes = localizar_municipios(
        [_convenio("1")], [_meta("1", "Recife", "pe")]
    )

    assert localizacoes == [
        {"nr_convenio": "1", "municipio": "RECIFE", "uf": "PE", "fonte_municipio": "meta"}
    ]


def test_sem_meta_usa_municipio_da_gold() -> None:
    """Ramo "sede" do I1b: hoje não é alcançado (#80 esvaziou a coluna)."""
    gold = [_convenio("1", municipio_execucao="Natal", uf_execucao="RN")]

    [local] = localizar_municipios(gold, [])

    assert (local["municipio"], local["uf"], local["fonte_municipio"]) == (
        "NATAL", "RN", "sede",
    )


def test_meta_tem_precedencia_sobre_a_gold() -> None:
    gold = [_convenio("1", municipio_execucao="BRASÍLIA", uf_execucao="DF")]

    [local] = localizar_municipios(gold, [_meta("1", "MANAUS", "AM")])

    assert (local["municipio"], local["uf"]) == ("MANAUS", "AM")


def test_sem_municipio_em_nenhuma_fonte_fica_fora() -> None:
    """Hoje é o caso da maioria: sem meta e com a gold em branco (#80)."""
    gold = [_convenio("1"), _convenio("2")]

    localizacoes = localizar_municipios(gold, [_meta("2", "", "")])

    assert localizacoes == []


@pytest.mark.parametrize(
    "meta_incompleta",
    [("", "SP"), ("CAMPINAS", ""), ("CAMPINAS", "S"), (None, None)],
    ids=["sem_municipio", "sem_uf", "uf_invalida", "nulos"],
)
def test_meta_sem_municipio_ou_uf_valida_e_ignorada(meta_incompleta) -> None:
    municipio, uf = meta_incompleta
    gold = [_convenio("1", municipio_execucao="SANTOS", uf_execucao="SP")]

    [local] = localizar_municipios(gold, [_meta("1", municipio, uf)])

    assert (local["municipio"], local["fonte_municipio"]) == ("SANTOS", "sede")


def test_grafias_diferentes_do_mesmo_municipio_contam_uma_vez() -> None:
    gold = [_convenio("1"), _convenio("2")]
    metas = [_meta("1", "São Paulo", "SP"), _meta("2", " SAO  PAULO ", "SP")]

    [nacional] = calcular_cobertura_nacional(localizar_municipios(gold, metas))

    assert nacional["municipios_atendidos"] == 1
    assert nacional["n_instrumentos"] == 2


def test_homonimos_em_ufs_diferentes_contam_separado() -> None:
    gold = [_convenio("1"), _convenio("2")]
    metas = [_meta("1", "BOM JESUS", "PI"), _meta("2", "BOM JESUS", "RS")]

    [nacional] = calcular_cobertura_nacional(localizar_municipios(gold, metas))

    assert nacional["municipios_atendidos"] == 2


def test_instrumento_com_metas_em_varios_municipios_atende_todos() -> None:
    """Cobertura conta presença; não reparte valor, então não há "Múltiplas"."""
    metas = [
        _meta("1", "SALVADOR", "BA"),
        _meta("1", "SALVADOR", "BA"),
        _meta("1", "ILHÉUS", "BA"),
        _meta("1", "ARACAJU", "SE"),
    ]

    localizacoes = localizar_municipios([_convenio("1")], metas)
    [nacional] = calcular_cobertura_nacional(localizacoes)
    por_uf = {u["uf"]: u for u in calcular_cobertura_uf(localizacoes)}

    assert nacional["municipios_atendidos"] == 3
    assert nacional["n_instrumentos"] == 1
    contagem = {
        uf: (u["municipios_atendidos"], u["n_instrumentos"]) for uf, u in por_uf.items()
    }
    assert contagem == {"BA": (2, 1), "SE": (1, 1)}


def test_ufs_com_municipio_batem_com_o_i1b() -> None:
    """Instrumento de UF única no I1b fica na mesma UF no I9; "Sem UF" fica fora."""
    gold = [
        _convenio("1"),
        _convenio("2"),
        _convenio("3", municipio_execucao="CUIABÁ", uf_execucao="MT"),
        _convenio("4"),
    ]
    metas = [
        _meta("1", "BELÉM", "PA"),
        _meta("2", "SANTARÉM", "PA"),
        _meta("2", "MARABÁ", "PA"),
    ]

    i1b = {
        i["nr_convenio"]: i["uf"]
        for i in montar_instrumentos_i1b(gold, metas)
        if i["fonte_uf"] != "sem_informacao"
    }
    i9 = {loc["nr_convenio"]: loc["uf"] for loc in localizar_municipios(gold, metas)}

    assert i9 == i1b == {"1": "PA", "2": "PA", "3": "MT"}


# ---------------------------------------------------------------------------
# Cobertura nacional
# ---------------------------------------------------------------------------
def test_cobertura_nacional_percentual_sobre_5570() -> None:
    localizacoes = [_local(str(i), f"MUN{i}", "SP") for i in range(10)]

    [nacional] = calcular_cobertura_nacional(localizacoes)

    assert nacional["cobertura_pct"] == round(10 / 5570 * 100, 2)
    assert nacional["total_municipios_brasil"] == 5570


def test_cobertura_nacional_conta_instrumentos_distintos() -> None:
    localizacoes = [
        _local("1", "A", "SP"), _local("2", "A", "SP"), _local("2", "B", "SP"),
    ]

    [nacional] = calcular_cobertura_nacional(localizacoes)

    assert nacional["municipios_atendidos"] == 2
    assert nacional["n_instrumentos"] == 2


def test_cobertura_nacional_sem_localizacao_e_zero() -> None:
    [nacional] = calcular_cobertura_nacional([])

    assert (nacional["municipios_atendidos"], nacional["cobertura_pct"]) == (0, 0.0)
    assert nacional["n_instrumentos"] == 0


# ---------------------------------------------------------------------------
# Cobertura por UF
# ---------------------------------------------------------------------------
def test_cobertura_uf_usa_total_do_cadastro() -> None:
    [uf] = calcular_cobertura_uf([_local("1", "CUIABÁ", "MT")])

    assert uf["total_municipios_uf"] == 142
    assert uf["cobertura_pct"] == round(1 / 142 * 100, 2)


def test_cobertura_uf_vazia_quando_total_uf_ausente() -> None:
    """UF fora do cadastro (não deveria acontecer, mas não quebra)."""
    [uf] = calcular_cobertura_uf([_local("1", "X", "ZZ")])

    assert uf["total_municipios_uf"] == 0
    assert uf["cobertura_pct"] == ""


def test_cobertura_uf_ordenada_por_municipios_desc_e_uf() -> None:
    localizacoes = [
        _local("1", "A", "SP"), _local("2", "B", "SP"),
        _local("3", "C", "RJ"), _local("4", "D", "AL"),
    ]

    ufs = calcular_cobertura_uf(localizacoes)

    assert [u["uf"] for u in ufs] == ["SP", "AL", "RJ"]


# ---------------------------------------------------------------------------
# Regressão da fórmula — contra os resultados entregues pelo BI
# ---------------------------------------------------------------------------
def test_regressao_cobertura_nacional() -> None:
    [esperado] = _ler_fixture(FIXTURES_I9, "i9_convenio_cobertura_nacional.csv")

    [obtido] = calcular_cobertura_nacional(_localizacoes_da_fixture_i1())

    assert obtido["municipios_atendidos"] == int(esperado["municipios_atendidos"])
    assert obtido["total_municipios_brasil"] == int(esperado["total_municipios_brasil"])
    assert obtido["cobertura_pct"] == pytest.approx(
        float(esperado["cobertura_pct"]), abs=0.011
    )
    assert obtido["n_instrumentos"] == int(esperado["n_instrumentos"])


def test_regressao_cobertura_uf() -> None:
    esperado = {
        e["uf"]: e for e in _ler_fixture(FIXTURES_I9, "i9_convenio_cobertura_uf.csv")
    }

    obtido = {o["uf"]: o for o in calcular_cobertura_uf(_localizacoes_da_fixture_i1())}

    assert set(obtido) == set(esperado)
    for uf, e in esperado.items():
        o = obtido[uf]
        assert o["municipios_atendidos"] == int(e["municipios_atendidos"])
        assert o["total_municipios_uf"] == int(e["total_municipios_uf"])
        assert o["n_instrumentos"] == int(e["n_instrumentos"])
        assert o["cobertura_pct"] == pytest.approx(float(e["cobertura_pct"]), abs=0.011)


# ---------------------------------------------------------------------------
# Saídas — nome e colunas são contrato do export para o Power BI
# ---------------------------------------------------------------------------
def test_calcular_i9_mantem_nomes_e_colunas_das_saidas() -> None:
    saidas = calcular_i9([_convenio("1")], [_meta("1", "CUIABÁ", "MT")])

    assert set(saidas) == {"i9_convenio_cobertura_nacional", "i9_convenio_cobertura_uf"}
    [nacional] = saidas["i9_convenio_cobertura_nacional"]
    [uf] = saidas["i9_convenio_cobertura_uf"]
    assert list(nacional) == [
        "municipios_atendidos",
        "total_municipios_brasil",
        "cobertura_pct",
        "n_instrumentos",
    ]
    assert list(uf) == [
        "uf",
        "municipios_atendidos",
        "total_municipios_uf",
        "cobertura_pct",
        "n_instrumentos",
    ]
