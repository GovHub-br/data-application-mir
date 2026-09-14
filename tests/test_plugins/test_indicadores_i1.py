"""Testes do indicador I1 — Valor Executado por Instrumento.

Cada teste unitário cobre uma decisão metodológica registrada no script
original da equipe de BI (i1_valor_executado.py / i1_etapa_cadeia_ted.R).
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
# Helpers
# ---------------------------------------------------------------------------
def _plano(id_plano_acao, situacao="APROVADO", sq="900", **extra):
    base = {
        "id_plano_acao": id_plano_acao,
        "sq_instrumento": sq,
        "tx_situacao_plano_acao": situacao,
        "aa_ano_plano_acao": 2024,
        "sigla_unidade_descentralizada": "UFX",
        "unidade_descentralizada": "Universidade X",
        "vl_total_plano_acao": Decimal("1000.00"),
        "in_forma_execucao_direta": False,
        "in_forma_execucao_particulares": False,
        "in_forma_execucao_descentralizada": False,
    }
    base.update(extra)
    return base


def _resumo(plano_acao, empenhado=0, anulado=0, liquidado=0, pago_ex=0, pago_rap=0,
            programa=None):
    return {
        "plano_acao": plano_acao,
        "empenhado": empenhado,
        "empenho_anulado": anulado,
        "despesas_liquidada": liquidado,
        "despesas_pagas_exercicio": pago_ex,
        "despesas_pagas_rap": pago_rap,
        "programa_governo": programa,
    }


def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              parlamentares=None, empenhado=100, **extra):
    base = {
        "nr_convenio": nr,
        "modalidade_instrumento": "CONVENIO",
        "parlamentares": parlamentares,
        "data_assinatura": assinatura,
        "inicio_vigencia": vigencia,
        "situacao_atual": situacao,
        "uf_execucao": "DF",
        "municipio_execucao": "BRASÍLIA",
        "nome_convenente": "Prefeitura",
        "categoria_convenente": "Administração Pública Municipal",
        "valor_firmado_atualizado": 200,
        "valor_empenhado": empenhado,
        "valor_total_pago": 50,
    }
    base.update(extra)
    return base


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

    teds = calcular_teds(planos, resumo=[], instrumentos_emendas=[])

    assert [t["id_plano_acao"] for t in teds] == ["1"]


def test_ted_empenhado_liquido_soma_todas_as_linhas_do_resumo() -> None:
    """Decisão 5: várias num_transf do mesmo plano são SOMADAS, não deduplicadas."""
    planos = [_plano(1429)]
    resumo = [
        _resumo(1429, empenhado=Decimal("1994300.00"), anulado=Decimal("300.00")),
        _resumo(1429, empenhado=0, anulado=0),
    ]

    [ted] = calcular_teds(planos, resumo, instrumentos_emendas=[])

    assert ted["empenhado_bruto"] == 1994300.0
    assert ted["empenho_anulado"] == 300.0
    assert ted["empenhado_liquido"] == 1994000.0
    assert ted["n_linhas_resumo"] == 2


def test_ted_pago_soma_exercicio_e_rap_e_liquidado() -> None:
    planos = [_plano(1)]
    resumo = [_resumo(1, liquidado=10, pago_ex=7.5, pago_rap=2.5)]

    [ted] = calcular_teds(planos, resumo, instrumentos_emendas=[])

    assert ted["liquidado"] == 10.0
    assert ted["pago"] == 10.0


def test_ted_sem_linha_no_resumo_fica_com_zeros() -> None:
    planos = [_plano(1, vl_total_plano_acao=Decimal("239652.27"))]

    [ted] = calcular_teds(planos, resumo=[], instrumentos_emendas=[])

    assert ted["vl_firmado"] == 239652.27
    assert ted["empenhado_liquido"] == 0.0
    assert ted["pago"] == 0.0
    assert ted["n_linhas_resumo"] == 0


def test_ted_origem_emenda_via_sq_instrumento() -> None:
    """Decisão 6: origem marcada no grão de instrumento via instrumentos_emendas."""
    planos = [_plano(2662, sq="111"), _plano(1, sq="222")]
    emendas = [
        {"tipo_instrumento": "TED", "numero_instrumento": "111"},
        {"tipo_instrumento": "TED", "numero_instrumento": "111"},  # 2ª NE, mesmo TED
        {"tipo_instrumento": "Convênio", "numero_instrumento": "222"},
    ]

    teds = calcular_teds(planos, resumo=[], instrumentos_emendas=emendas)

    assert {t["id_plano_acao"]: t["origem"] for t in teds} == {
        "2662": "emenda",
        "1": "orcamento_regular",
    }


def test_ted_forma_execucao_2n_e_desagregacao_nao_filtro() -> None:
    """Decisão 4: as flags descrevem, não filtram."""
    planos = [
        _plano(1, in_forma_execucao_direta=True, in_forma_execucao_descentralizada=True),
        _plano(2),
    ]

    teds = calcular_teds(planos, resumo=[], instrumentos_emendas=[])

    assert teds[0]["forma_execucao_2n"] == "direta; descentralizada"
    assert teds[1]["forma_execucao_2n"] == ""
    assert len(teds) == 2


def test_ted_aceita_flags_em_texto_como_no_csv_original() -> None:
    planos = [_plano(1, in_forma_execucao_particulares="SIM")]

    [ted] = calcular_teds(planos, resumo=[], instrumentos_emendas=[])

    assert ted["forma_execucao_2n"] == "particulares"


def test_ted_programa_governo_vem_da_primeira_linha_preenchida() -> None:
    planos = [_plano(1)]
    resumo = [
        _resumo(1, programa=None),
        _resumo(1, programa="5804"),
        _resumo(1, programa="9999"),
    ]

    [ted] = calcular_teds(planos, resumo, instrumentos_emendas=[])

    assert ted["programa_governo"] == "5804"


def test_ted_etapa_cadeia_vazia_quando_fora_da_definicao_b() -> None:
    """Decisão 7: universos do I1 e da Definição B não coincidem."""
    planos = [_plano(1), _plano(2)]

    teds = calcular_teds(planos, [], [], etapa_por_plano={"1": "S4_cadeia_plena"})

    assert teds[0]["etapa_cadeia"] == "S4_cadeia_plena"
    assert teds[1]["etapa_cadeia"] == ""


def test_ted_campos_descritivos() -> None:
    [ted] = calcular_teds([_plano(2532, sq="955606")], [], [])

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
        _plano(1, in_forma_execucao_descentralizada=True),   # entra pela flag
        _plano(2),                                            # entra pela NC
        _plano(3),                                            # fora
    ]
    nc = [{"id_plano_acao": 2}]

    etapas = classificar_etapa_cadeia(planos, pf=[], nc=nc, ne=[])

    assert set(etapas) == {"1", "2"}


def test_etapa_cadeia_classificacao_por_estagio() -> None:
    planos = [_plano(i, in_forma_execucao_descentralizada=True) for i in range(1, 6)]
    pf = [{"id_plano_acao": 2}, {"id_plano_acao": 3}, {"id_plano_acao": 5}]
    nc = [{"id_plano_acao": 3}, {"id_plano_acao": 4}, {"id_plano_acao": 5}]
    ne = [{"plano_acao": 5}, {"plano_acao": None}]

    etapas = classificar_etapa_cadeia(planos, pf, nc, ne)

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
    gold = [_convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01")]

    convenios = calcular_convenios(gold)

    assert [c["nr_convenio"] for c in convenios] == ["2"]
    assert convenios[0]["ano"] == 2023
    assert convenios[0]["ano_fonte"] == "data_assinatura"


def test_convenio_ano_fallback_para_inicio_vigencia() -> None:
    gold = [_convenio(1, assinatura=None, vigencia="2024-05-10")]

    [c] = calcular_convenios(gold)

    assert c["ano"] == 2024
    assert c["ano_fonte"] == "inicio_vigencia"


def test_convenio_sem_nenhuma_data_fica_fora() -> None:
    gold = [_convenio(1, assinatura=None, vigencia=None)]

    assert calcular_convenios(gold) == []


def test_convenio_aceita_datas_tipadas_do_postgres() -> None:
    gold = [_convenio(1, assinatura=date(2025, 2, 3))]

    [c] = calcular_convenios(gold)

    assert c["ano"] == 2025


def test_convenio_exclui_cancelado_e_anulado() -> None:
    gold = [
        _convenio(1, situacao="Cancelado"),
        _convenio(2, situacao="Convênio Anulado"),
        _convenio(3, situacao="Convenio Anulado"),
        _convenio(4, situacao="Aguardando Prestação de Contas"),
    ]

    convenios = calcular_convenios(gold)

    assert [c["nr_convenio"] for c in convenios] == ["4"]


def test_convenio_origem_emenda_quando_ha_parlamentar() -> None:
    gold = [_convenio(1, parlamentares="Deputado X"), _convenio(2, parlamentares="  ")]

    convenios = calcular_convenios(gold)

    assert convenios[0]["origem"] == "emenda"
    assert convenios[1]["origem"] == "orcamento_regular"


def test_convenio_sem_empenho_permanece_na_contagem() -> None:
    """Decisão 3c: empenhado zero/vazio fica no universo, marcado."""
    gold = [_convenio(1, empenhado=None), _convenio(2, empenhado=Decimal("300000.00"))]

    convenios = calcular_convenios(gold)

    assert [c["sem_empenho"] for c in convenios] == [1, 0]
    assert convenios[0]["empenhado_liquido"] == 0.0
    assert convenios[1]["empenhado_liquido"] == 300000.0


def test_convenio_campos_descritivos() -> None:
    gold = [_convenio(972607, modalidade_instrumento="TERMO DE FOMENTO")]

    [c] = calcular_convenios(gold)

    assert c["instrumento"] == "TERMO DE FOMENTO"
    assert c["nr_convenio"] == "972607"
    assert c["uf_execucao"] == "DF"
    assert c["municipio_execucao"] == "BRASÍLIA"
    assert c["convenente"] == "Prefeitura"
    assert c["categoria_convenente"] == "Administração Pública Municipal"
    assert c["vl_firmado"] == 200.0
    assert c["pago"] == 50.0


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
    gold = [_convenio(1, uf_execucao=None, municipio_execucao="")]
    convenios = calcular_convenios(gold)

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
        [_plano(1, sq="111"), _plano(2, sq="222")],
        [_resumo(1, empenhado=600), _resumo(2, empenhado=200)],
        [{"tipo_instrumento": "TED", "numero_instrumento": "111"}],
    )
    convenios = calcular_convenios([
        _convenio(1, empenhado=100, parlamentares="Dep. Y"),
        _convenio(2, empenhado=100, parlamentares="Dep. Z"),
    ])

    carteira = calcular_carteira(teds, convenios)

    assert [(c["instrumento"], c["origem"], c["n_instrumentos"]) for c in carteira] == [
        ("TED", "emenda", 1),
        ("TED", "orcamento_regular", 1),
        ("CONVENIO", "emenda", 2),
    ]
    assert [c["share_pct"] for c in carteira] == [60.0, 20.0, 20.0]
    assert all(c["leitura"] == "carteira_sem_territorio" for c in carteira)


def test_carteira_share_zero_quando_nao_ha_empenho() -> None:
    carteira = calcular_carteira(calcular_teds([_plano(1)], [], []), [])

    assert carteira[0]["share_pct"] == 0


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i1_devolve_as_seis_saidas() -> None:
    saidas = calcular_i1(
        planos=[_plano(1, in_forma_execucao_descentralizada=True)],
        resumo=[_resumo(1, empenhado=10)],
        instrumentos_emendas=[],
        gold_convenios=[_convenio(1)],
        pf=[{"id_plano_acao": 1}],
        nc=[],
        ne=[],
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
