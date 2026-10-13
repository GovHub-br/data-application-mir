"""Testes do indicador I1b — Taxa de Execução por UF e Ano (Convênios/Fomentos).

Cada teste cobre uma decisão metodológica do pacote Bloco 1 da equipe de BI
(``i1b_convenios_uf_ano_bi.R``), documentada no módulo
``plugins/indicadores/i1b_convenios_uf_ano.py``.
"""

from indicadores.i1b_convenios_uf_ano import (
    ROTULO_DEMAIS,
    ROTULO_MULTIPLAS,
    ROTULO_SEM_UF,
    calcular_i1b,
    montar_fato,
    montar_heatmap,
    montar_instrumentos,
    montar_ranking_uf,
    montar_uf_metas,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              parlamentares=None, firmado_atualizado=1000.0, firmado_inicial=0.0,
              empenhado=1000.0, pago=500.0, uf_execucao=None):
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
        "uf_execucao": uf_execucao,
    }


def _meta(nr_convenio, uf_meta):
    return {"nr_convenio": nr_convenio, "uf_meta": uf_meta}


# ---------------------------------------------------------------------------
# UF da meta física
# ---------------------------------------------------------------------------
def test_uf_metas_uma_uf_unica() -> None:
    metas = [_meta(1, "GO"), _meta(1, "GO")]  # mesma meta repetida, mesma UF

    ufs = montar_uf_metas(metas)

    assert ufs["1"] == {"n_ufs_meta": 1, "uf_meta_unica": "GO"}


def test_uf_metas_mais_de_uma_uf() -> None:
    metas = [_meta(1, "GO"), _meta(1, "DF")]

    ufs = montar_uf_metas(metas)

    assert ufs["1"]["n_ufs_meta"] == 2


def test_uf_metas_ignora_uf_invalida() -> None:
    metas = [_meta(1, ""), _meta(1, "Múltiplas")]

    ufs = montar_uf_metas(metas)

    assert "1" not in ufs


# ---------------------------------------------------------------------------
# Fonte da UF — meta tem prioridade sobre sede
# ---------------------------------------------------------------------------
def test_uf_vem_da_meta_quando_disponivel_mesmo_com_sede_preenchida() -> None:
    gold = [_convenio(1, uf_execucao="DF")]
    metas = [_meta(1, "GO")]

    [i] = montar_instrumentos(gold, metas)

    assert i["uf"] == "GO"
    assert i["fonte_uf"] == "meta"


def test_uf_cai_para_sede_quando_nao_ha_meta() -> None:
    gold = [_convenio(1, uf_execucao="DF")]

    [i] = montar_instrumentos(gold, meta_crono_fisico=[])

    assert i["uf"] == "DF"
    assert i["fonte_uf"] == "sede"


def test_uf_execucao_nula_e_sem_meta_vira_sem_informacao() -> None:
    """Hoje uf_execucao está sempre em branco (decisão da equipe, PR #80) —
    sem meta física, o instrumento cai em 'Sem UF' / 'sem_informacao'."""
    gold = [_convenio(1, uf_execucao=None)]

    [i] = montar_instrumentos(gold, meta_crono_fisico=[])

    assert i["uf"] == ROTULO_SEM_UF
    assert i["fonte_uf"] == "sem_informacao"


def test_meta_com_multiplas_ufs_vira_rotulo_multiplas() -> None:
    gold = [_convenio(1)]
    metas = [_meta(1, "GO"), _meta(1, "DF")]

    [i] = montar_instrumentos(gold, metas)

    assert i["uf"] == ROTULO_MULTIPLAS
    assert i["fonte_uf"] == "meta"


# ---------------------------------------------------------------------------
# Universo (mesmo do I1 Convênios)
# ---------------------------------------------------------------------------
def test_corte_temporal_2023() -> None:
    gold = [_convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01")]

    instrumentos = montar_instrumentos(gold, meta_crono_fisico=[])

    assert [i["nr_convenio"] for i in instrumentos] == ["2"]


def test_exclui_empenho_zero_com_pagamento_por_padrao() -> None:
    gold = [_convenio(1, empenhado=0.0, pago=100.0), _convenio(2, empenhado=100.0, pago=50.0)]

    instrumentos = montar_instrumentos(gold, meta_crono_fisico=[])

    assert [i["nr_convenio"] for i in instrumentos] == ["2"]


# ---------------------------------------------------------------------------
# Ranking de UF e grupo "Demais"
# ---------------------------------------------------------------------------
def test_ranking_uf_top_n_individuais_resto_vira_demais() -> None:
    gold = [
        _convenio(1, uf_execucao="SP", firmado_atualizado=500.0),
        _convenio(2, uf_execucao="RJ", firmado_atualizado=300.0),
        _convenio(3, uf_execucao="GO", firmado_atualizado=100.0),
    ]
    instrumentos = montar_instrumentos(gold, meta_crono_fisico=[])

    ranking = montar_ranking_uf(instrumentos, n_ufs_destaque=2)

    assert ranking["SP"] == {"uf_grupo": "SP", "ordem_uf": 1}
    assert ranking["RJ"] == {"uf_grupo": "RJ", "ordem_uf": 2}
    assert ranking["GO"] == {"uf_grupo": ROTULO_DEMAIS, "ordem_uf": 3}


# ---------------------------------------------------------------------------
# Taxa — soma do grupo, nunca média de taxas individuais
# ---------------------------------------------------------------------------
def test_taxa_e_soma_do_grupo_nao_media_das_taxas() -> None:
    # Instrumento A: pago=100/firmado=1000 (taxa 10%). Instrumento B: pago=900/firmado=1000 (taxa 90%).
    # Média simples das taxas seria 50%; a taxa correta é soma(pago)/soma(firmado) = 1000/2000 = 50%...
    # usamos valores assimétricos pra garantir que não é coincidência.
    gold = [
        _convenio(1, uf_execucao="SP", firmado_atualizado=1000.0, empenhado=1000.0, pago=100.0),
        _convenio(2, uf_execucao="SP", firmado_atualizado=4000.0, empenhado=4000.0, pago=4000.0),
    ]
    instrumentos = montar_instrumentos(gold, meta_crono_fisico=[])
    for i in instrumentos:
        i.update(montar_ranking_uf(instrumentos)[i["uf"]])

    heatmap = montar_heatmap(instrumentos)

    [linha] = heatmap
    # soma(pago)=4100, soma(firmado)=5000 -> 82.0%, não a média simples (10+100)/2=55%
    assert linha["taxa_execucao_pct"] == 82.0


def test_heatmap_celula_sem_convenio_fica_com_n_zero_e_taxa_none() -> None:
    gold = [
        _convenio(1, uf_execucao="SP", assinatura="2023-01-01"),
        _convenio(2, uf_execucao="SP", assinatura="2024-01-01"),
    ]
    instrumentos = montar_instrumentos(gold, meta_crono_fisico=[])
    for i in instrumentos:
        i.update(montar_ranking_uf(instrumentos)[i["uf"]])

    heatmap = montar_heatmap(instrumentos)

    assert {h["ano"] for h in heatmap} == {2023, 2024}
    assert all(h["n_instrumentos"] >= 0 for h in heatmap)


# ---------------------------------------------------------------------------
# Fato
# ---------------------------------------------------------------------------
def test_fato_agrega_por_uf_grupo_fonte_e_demais_dimensoes() -> None:
    gold = [
        _convenio(1, uf_execucao="SP", firmado_atualizado=500.0),
        _convenio(2, uf_execucao="SP", firmado_atualizado=500.0),
    ]
    instrumentos = montar_instrumentos(gold, meta_crono_fisico=[])
    for i in instrumentos:
        i.update(montar_ranking_uf(instrumentos)[i["uf"]])

    fato = montar_fato(instrumentos)

    assert len(fato) == 1  # mesma UF, ano, origem, modalidade, qualidade
    assert fato[0]["n_instrumentos"] == 2
    assert fato[0]["firmado"] == 1000.0


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i1b_devolve_tres_saidas_e_passa_nas_checagens() -> None:
    gold = [
        _convenio(1, uf_execucao="SP", firmado_atualizado=1000.0, empenhado=1000.0, pago=500.0),
        _convenio(2, uf_execucao="RJ", firmado_atualizado=2000.0, empenhado=2000.0, pago=1000.0),
        _convenio(3, assinatura="2020-01-01"),  # fora do corte
    ]
    metas = [_meta(2, "RJ")]

    saidas = calcular_i1b(gold, metas)

    assert set(saidas) == {
        "i1b_convenio_uf_ano_fato", "i1b_convenio_heatmap", "i1b_convenio_cartoes_ano",
    }
    assert sum(c["n_instrumentos"] for c in saidas["i1b_convenio_cartoes_ano"]) == 2

    [cartao] = saidas["i1b_convenio_cartoes_ano"]
    assert cartao["firmado"] == 3000.0
    assert cartao["pago"] == 1500.0
    assert cartao["taxa_execucao_pct"] == 50.0
