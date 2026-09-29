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


def _nc(sk_plano_acao, ptres):
    """Linha de mir_teds.fato_credito_descentralizado (só as colunas usadas)."""
    return {"sk_plano_acao": sk_plano_acao, "ptres": ptres}


def _acao(ptres, codigo_programa):
    """Linha de mir_teds.dim_acao_orcamentaria (só as colunas usadas)."""
    return {"ptres": ptres, "codigo_programa": codigo_programa}


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


def test_ted_programa_governo_e_o_maior_programa_das_ncs() -> None:
    """Decisão 8: max(programa) das NCs do plano, como no gold antigo."""
    planos = [_plano(1), _plano(2), _plano(3)]
    acoes = [_acao("172001", "5802"), _acao("172002", "5804")]
    creditos = [
        _nc(1, "172001"), _nc(1, "172002"), _nc(1, "172001"),
        _nc(2, "172001"),
        _nc(3, "-9"),
    ]

    teds = calcular_teds(planos, [], creditos, acoes)

    assert [t["programa_governo"] for t in teds] == ["5804", "5802", ""]


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
        creditos_teds=[],
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
