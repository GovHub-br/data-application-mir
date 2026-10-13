"""Testes do indicador I8 (TED) — Densidade por Secretaria.

Cada teste cobre uma decisão metodológica do pacote Bloco 1 da equipe de BI
(``i8_ted_bi.R``), documentada no módulo
``plugins/indicadores/i8_ted_densidade.py``.
"""

from indicadores.i8_ted_densidade import (
    ROTULO_SEM_SECRETARIA,
    calcular_i8,
    montar_barras,
    montar_cartao,
    montar_fato,
    montar_por_ano,
    montar_secretaria_e_nomes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _plano(id_plano_acao, id_programa=1, situacao="APROVADO", ano=2024, firmado=1000.0):
    return {
        "id_plano_acao": id_plano_acao,
        "id_programa": id_programa,
        "tx_situacao_plano_acao": situacao,
        "aa_ano_plano_acao": ano,
        "vl_total_plano_acao": firmado,
    }


def _programa(id_programa, secretaria="SQPT", nome="Secretaria de Políticas"):
    return {
        "id_programa": id_programa,
        "sigla_unidade_responsavel_acompanhamento": secretaria,
        "unidade_responsavel_acompanhamento": nome,
    }


def _resumo(plano_acao, origem):
    return {"plano_acao": plano_acao, "origem": origem}


# ---------------------------------------------------------------------------
# Fato (mesma lógica do I4 — testada aqui de novo porque é um módulo próprio)
# ---------------------------------------------------------------------------
def test_fato_rejeitado_fica_fora() -> None:
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    fato = montar_fato(planos, prog=[], resumo=[])

    assert [f["id_plano_acao"] for f in fato] == ["1"]


def test_fato_sem_secretaria_identificada() -> None:
    planos = [_plano(1, id_programa=999)]

    [f] = montar_fato(planos, prog=[_programa(1)], resumo=[])

    assert f["secretaria"] == ROTULO_SEM_SECRETARIA


# ---------------------------------------------------------------------------
# Agregações — diferença chave do I4: ordenado por Nº DE TEDS, não por valor
# ---------------------------------------------------------------------------
def test_barras_ordenadas_por_quantidade_de_teds_nao_por_valor() -> None:
    planos = [
        # SECA: 1 TED, valor alto. SECB: 2 TEDs, valor total menor.
        _plano(1, id_programa=1, firmado=900.0),
        _plano(2, id_programa=2, firmado=100.0),
        _plano(3, id_programa=2, firmado=100.0),
    ]
    prog = [_programa(1, secretaria="SECA"), _programa(2, secretaria="SECB")]
    fato = montar_fato(planos, prog, resumo=[])
    _, nomes = montar_secretaria_e_nomes(prog)

    barras = montar_barras(fato, nomes)

    assert [b["secretaria"] for b in barras] == ["SECB", "SECA"]
    assert barras[0]["n_teds"] == 2
    assert barras[0]["pct_do_total_teds"] == round(100 * 2 / 3, 1)
    assert barras[1]["n_teds"] == 1


def test_valor_medio_por_ted_e_firmado_dividido_pela_quantidade() -> None:
    planos = [_plano(1, id_programa=1, firmado=300.0), _plano(2, id_programa=1, firmado=700.0)]
    prog = [_programa(1, secretaria="SECA")]
    fato = montar_fato(planos, prog, resumo=[])
    _, nomes = montar_secretaria_e_nomes(prog)

    [barra] = montar_barras(fato, nomes)

    assert barra["firmado"] == 1000.0
    assert barra["n_teds"] == 2
    assert barra["valor_medio_por_ted"] == 500.0


def test_por_ano_percentual_e_fatia_da_quantidade_de_teds_do_ano() -> None:
    planos = [
        _plano(1, id_programa=1, ano=2023, firmado=100.0),
        _plano(2, id_programa=2, ano=2023, firmado=100.0),
        _plano(3, id_programa=2, ano=2023, firmado=100.0),
    ]
    prog = [_programa(1, secretaria="SECA"), _programa(2, secretaria="SECB")]
    fato = montar_fato(planos, prog, resumo=[])
    _, nomes = montar_secretaria_e_nomes(prog)

    por_ano = montar_por_ano(fato, nomes)

    linha_seca = next(l for l in por_ano if l["secretaria"] == "SECA")
    linha_secb = next(l for l in por_ano if l["secretaria"] == "SECB")
    assert linha_seca["pct_do_total_teds_ano"] == round(100 * 1 / 3, 1)
    assert linha_secb["pct_do_total_teds_ano"] == round(100 * 2 / 3, 1)


def test_cartao_distingue_mais_instrumentos_de_maior_porte_medio() -> None:
    planos = [
        # SECA: 2 TEDs baratos (mais instrumentos). SECB: 1 TED caro (maior porte médio).
        _plano(1, id_programa=1, firmado=10.0),
        _plano(2, id_programa=1, firmado=10.0),
        _plano(3, id_programa=2, firmado=500.0),
    ]
    prog = [_programa(1, secretaria="SECA"), _programa(2, secretaria="SECB")]
    fato = montar_fato(planos, prog, resumo=[])
    _, nomes = montar_secretaria_e_nomes(prog)
    barras = montar_barras(fato, nomes)

    [cartao] = montar_cartao(fato, barras)

    assert cartao["secretaria_mais_instrumentos"] == "SECA"
    assert cartao["n_teds_mais_instrumentos"] == 2
    assert cartao["secretaria_maior_porte_medio"] == "SECB"
    assert cartao["valor_medio_maior_porte"] == 500.0
    assert cartao["n_teds"] == 3
    assert cartao["firmado_total"] == 520.0


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i8_devolve_quatro_saidas_e_passa_nas_checagens() -> None:
    planos = [
        _plano(1, id_programa=1, ano=2023, firmado=1000.0),
        _plano(2, id_programa=2, ano=2024, firmado=2000.0),
        _plano(3, situacao="REJEITADO"),
    ]
    prog = [_programa(1, secretaria="SECA"), _programa(2, secretaria="SECB")]
    resumo = [_resumo(1, "Emenda - X"), _resumo(2, "Recurso Próprio")]

    saidas = calcular_i8(planos, prog, resumo)

    assert set(saidas) == {
        "i8_ted_densidade_fato", "i8_ted_densidade_barras",
        "i8_ted_densidade_por_ano", "i8_ted_densidade_cartao",
    }
    assert len(saidas["i8_ted_densidade_fato"]) == 2  # REJEITADO fora

    [cartao] = saidas["i8_ted_densidade_cartao"]
    assert cartao["firmado_total"] == 3000.0
    assert cartao["n_teds"] == 2
