"""Testes do indicador I2 — Valor Médio por Executor/Convenente, por UF.

Cada teste cobre uma decisão metodológica do pacote Bloco 1 da equipe de BI
(``i2_ted_bi.R`` / ``i2_convenios_bi.R``), documentada no módulo
``plugins/indicadores/i2_concentracao_executores.py``.
"""

from indicadores.i2_concentracao_executores import (
    ROTULO_SEM_UF,
    calcular_i2,
    calcular_i2_convenios,
    calcular_i2_ted,
    montar_barras_convenio,
    montar_barras_ted,
    montar_fato_convenio,
    montar_fato_ted,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _plano(id_plano_acao, situacao="APROVADO", ano=2024, firmado=1000.0,
           sigla="UFBA", nome_unidade="Universidade Federal da Bahia"):
    return {
        "id_plano_acao": id_plano_acao,
        "tx_situacao_plano_acao": situacao,
        "aa_ano_plano_acao": ano,
        "vl_total_plano_acao": firmado,
        "sigla_unidade_descentralizada": sigla,
        "unidade_descentralizada": nome_unidade,
    }


def _resumo(plano_acao, origem):
    return {"plano_acao": plano_acao, "origem": origem}


def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              parlamentares=None, firmado_atualizado=1000.0, firmado_inicial=0.0,
              empenhado=1000.0, pago=500.0, convenente="Instituto X",
              uf_execucao=None, categoria=None):
    return {
        "nr_convenio": nr,
        "modalidade_instrumento": "CONVENIO",
        "parlamentares": parlamentares,
        "data_assinatura": assinatura,
        "inicio_vigencia": vigencia,
        "situacao_atual": situacao,
        "valor_firmado_atualizado": firmado_atualizado,
        "valor_firmado_inicial": firmado_inicial,
        "valor_empenhado": empenhado,
        "valor_total_pago": pago,
        "nome_convenente": convenente,
        "uf_execucao": uf_execucao,
        "categoria_convenente": categoria,
    }


# ---------------------------------------------------------------------------
# TED — executor e UF (sede, via dicionário)
# ---------------------------------------------------------------------------
def test_ted_rejeitado_fica_fora() -> None:
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    fato = montar_fato_ted(planos, resumo=[])

    assert [f["id_plano_acao"] for f in fato] == ["1"]


def test_ted_uf_vem_do_dicionario_por_sigla() -> None:
    [f] = montar_fato_ted([_plano(1, sigla="UFBA")], resumo=[])

    assert f["executor"] == "UFBA"
    assert f["uf"] == "BA"


def test_ted_sigla_ausente_corrigida_pelo_nome() -> None:
    [f] = montar_fato_ted(
        [_plano(1, sigla="", nome_unidade="Universidade Federal do Paraná")], resumo=[],
    )

    assert f["executor"] == "UFPR"
    assert f["uf"] == "PR"


def test_ted_sigla_ausente_sem_correcao_vira_sem_sigla_e_sem_uf() -> None:
    [f] = montar_fato_ted([_plano(1, sigla="", nome_unidade="Órgão Desconhecido")], resumo=[])

    assert f["executor"] == "Sem sigla"
    assert f["uf"] == ROTULO_SEM_UF


def test_ted_sigla_fora_do_dicionario_vira_sem_uf() -> None:
    [f] = montar_fato_ted([_plano(1, sigla="XYZ")], resumo=[])

    assert f["executor"] == "XYZ"
    assert f["uf"] == ROTULO_SEM_UF


def test_ted_origem_via_resumo_orcamentario() -> None:
    [f] = montar_fato_ted([_plano(1)], resumo=[_resumo(1, "Emenda - Dep. X")])

    assert f["origem"] == "Emenda"


def test_barras_ted_valor_medio_e_ponderado_por_executor_nao_media_de_medias() -> None:
    # UFBA: 1 executor, 2 TEDs, 900 total -> média 900.
    # UFC: 1 executor, 1 TED, 100 total -> média 100.
    planos = [
        _plano(1, sigla="UFBA", firmado=500.0),
        _plano(2, sigla="UFBA", firmado=400.0),
        _plano(3, sigla="UFC", firmado=100.0),
    ]
    fato = montar_fato_ted(planos, resumo=[])

    barras = montar_barras_ted(fato)

    por_uf = {b["uf_grupo"]: b for b in barras}
    assert por_uf["BA"]["valor_medio_por_executor"] == 900.0
    assert por_uf["CE"]["valor_medio_por_executor"] == 100.0
    assert por_uf["BA"]["media_nacional"] == por_uf["CE"]["media_nacional"]


def test_calcular_i2_ted_devolve_tres_saidas_e_passa_nas_checagens() -> None:
    planos = [
        _plano(1, sigla="UFBA", firmado=1000.0),
        _plano(2, sigla="UFC", firmado=2000.0),
        _plano(3, situacao="REJEITADO"),
    ]

    saidas = calcular_i2_ted(planos, resumo=[])

    assert set(saidas) == {"i2_ted_executor_uf_fato", "i2_ted_uf_barras", "i2_ted_cartao"}
    assert len(saidas["i2_ted_executor_uf_fato"]) == 2

    [cartao] = saidas["i2_ted_cartao"]
    assert cartao["firmado"] == 3000.0
    assert cartao["n_executores"] == 2


# ---------------------------------------------------------------------------
# Convênios/Fomentos — uf_execucao deixada em branco (decisão da equipe)
# ---------------------------------------------------------------------------
def test_convenio_corte_temporal_2023() -> None:
    gold = [_convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01")]

    instrumentos = montar_fato_convenio(gold)

    assert [i["nr_convenio"] for i in instrumentos] == ["2"]


def test_convenio_exclui_empenho_zero_com_pagamento_por_padrao() -> None:
    gold = [_convenio(1, empenhado=0.0, pago=100.0), _convenio(2, empenhado=100.0, pago=50.0)]

    instrumentos = montar_fato_convenio(gold)

    assert [i["nr_convenio"] for i in instrumentos] == ["2"]


def test_convenio_uf_execucao_nula_vira_sem_uf() -> None:
    """Decisão da equipe (João): uf_execucao fica NULL até o coleta mir existir —
    o indicador não quebra, só cai inteiro no grupo 'Sem UF' enquanto isso."""
    [i] = montar_fato_convenio([_convenio(1, uf_execucao=None)])

    assert i["uf"] == ROTULO_SEM_UF


def test_convenio_uf_execucao_invalida_tambem_vira_sem_uf() -> None:
    [i] = montar_fato_convenio([_convenio(1, uf_execucao="Múltiplas UFs")])

    assert i["uf"] == ROTULO_SEM_UF


def test_convenio_nome_normalizado_sem_acento_e_maiuscula() -> None:
    [i] = montar_fato_convenio([_convenio(1, convenente="Instituto de São José  ")])

    assert i["convenente"] == "INSTITUTO DE SAO JOSE"


def test_convenio_mesmo_convenente_conta_uma_vez_por_uf() -> None:
    """Como uf_execucao está sempre nula hoje, todo convenente cai no mesmo
    grupo 'Sem UF' — o teste já cobre esse caso degenerado."""
    gold = [
        _convenio(1, convenente="Instituto X", uf_execucao=None),
        _convenio(2, convenente="Instituto X", uf_execucao=None),
    ]
    instrumentos = montar_fato_convenio(gold)

    barras = montar_barras_convenio(instrumentos)

    [barra] = barras
    assert barra["uf_grupo"] == ROTULO_SEM_UF
    assert barra["n_convenentes"] == 1
    assert barra["n_instrumentos"] == 2


def test_calcular_i2_convenios_devolve_tres_saidas_e_passa_nas_checagens() -> None:
    gold = [
        _convenio(1, convenente="Instituto A", firmado_atualizado=1000.0, empenhado=1000.0),
        _convenio(2, convenente="Instituto B", firmado_atualizado=2000.0, empenhado=2000.0),
    ]

    saidas = calcular_i2_convenios(gold)

    assert set(saidas) == {
        "i2_convenio_convenente_uf_fato", "i2_convenio_uf_barras", "i2_convenio_cartao",
    }

    [cartao] = saidas["i2_convenio_cartao"]
    assert cartao["firmado"] == 3000.0
    assert cartao["n_convenentes"] == 2

    # Único grupo "Sem UF" hoje, já que uf_execucao está sempre em branco.
    [barra] = saidas["i2_convenio_uf_barras"]
    assert barra["uf_grupo"] == ROTULO_SEM_UF


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i2_devolve_as_seis_saidas() -> None:
    saidas = calcular_i2(
        planos=[_plano(1)],
        resumo=[],
        gold_convenios=[_convenio(1)],
    )

    assert set(saidas) == {
        "i2_ted_executor_uf_fato", "i2_ted_uf_barras", "i2_ted_cartao",
        "i2_convenio_convenente_uf_fato", "i2_convenio_uf_barras", "i2_convenio_cartao",
    }
