"""Testes do indicador I4 (TED) — Valor por Secretaria do MIR.

Cada teste cobre uma decisão metodológica do pacote Bloco 1 da equipe de BI
(``i4_ted_bi.R``), documentada no módulo
``plugins/indicadores/i4_ted_secretaria.py``.
"""

from indicadores.i4_ted_secretaria import (
    ROTULO_SEM_SECRETARIA,
    calcular_i4,
    calcular_origem_por_plano,
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
# Secretaria por programa
# ---------------------------------------------------------------------------
def test_secretaria_por_programa_mantem_primeira_ocorrencia() -> None:
    prog = [_programa(1, secretaria="SQPT"), _programa(1, secretaria="OUTRA")]

    secretarias, _ = montar_secretaria_e_nomes(prog)

    assert secretarias["1"] == "SQPT"


def test_nome_secretaria_pega_primeiro_nome_nao_vazio() -> None:
    prog = [_programa(1, secretaria="SQPT", nome=""), _programa(2, secretaria="SQPT", nome="Secretaria X")]

    _, nomes = montar_secretaria_e_nomes(prog)

    assert nomes["SQPT"] == "Secretaria X"


# ---------------------------------------------------------------------------
# Fato
# ---------------------------------------------------------------------------
def test_fato_rejeitado_fica_fora() -> None:
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    fato = montar_fato(planos, prog=[], resumo=[])

    assert [f["id_plano_acao"] for f in fato] == ["1"]


def test_fato_dedup_mantem_primeira_ocorrencia() -> None:
    planos = [_plano(1, firmado=100.0), _plano(1, firmado=999.0)]

    fato = montar_fato(planos, prog=[], resumo=[])

    assert len(fato) == 1
    assert fato[0]["firmado"] == 100.0


def test_fato_sem_secretaria_identificada() -> None:
    planos = [_plano(1, id_programa=999)]

    [f] = montar_fato(planos, prog=[_programa(1)], resumo=[])

    assert f["secretaria"] == ROTULO_SEM_SECRETARIA


def test_fato_secretaria_vinculada_por_programa() -> None:
    planos = [_plano(1, id_programa=42)]
    prog = [_programa(42, secretaria="SECAD")]

    [f] = montar_fato(planos, prog, resumo=[])

    assert f["secretaria"] == "SECAD"


def test_fato_origem_via_resumo_orcamentario() -> None:
    planos = [_plano(1)]
    resumo = [_resumo(1, "Emenda - Dep. X")]

    [f] = montar_fato(planos, prog=[], resumo=resumo)

    assert f["origem"] == "Emenda"


def test_origem_sem_informacao_quando_nao_bate_prefixo() -> None:
    origem = calcular_origem_por_plano([_resumo(1, "Tedinho (sem registro)")])

    assert origem["1"] == "Sem informação"


# ---------------------------------------------------------------------------
# Agregações
# ---------------------------------------------------------------------------
def test_barras_ordenadas_por_firmado_desc() -> None:
    planos = [
        _plano(1, id_programa=1, firmado=300.0),
        _plano(2, id_programa=2, firmado=700.0),
    ]
    prog = [_programa(1, secretaria="SECA"), _programa(2, secretaria="SECB")]
    fato = montar_fato(planos, prog, resumo=[])
    _, nomes = montar_secretaria_e_nomes(prog)

    barras = montar_barras(fato, nomes)

    assert [b["secretaria"] for b in barras] == ["SECB", "SECA"]
    assert barras[0]["pct_do_total"] == 70.0
    assert barras[0]["ordem_exibicao"] == 1


def test_por_ano_percentual_e_relativo_ao_total_do_ano() -> None:
    planos = [
        _plano(1, id_programa=1, ano=2023, firmado=100.0),
        _plano(2, id_programa=2, ano=2023, firmado=300.0),
        _plano(3, id_programa=1, ano=2024, firmado=50.0),
    ]
    prog = [_programa(1, secretaria="SECA"), _programa(2, secretaria="SECB")]
    fato = montar_fato(planos, prog, resumo=[])
    _, nomes = montar_secretaria_e_nomes(prog)

    por_ano = montar_por_ano(fato, nomes)

    linha_2023_seca = next(l for l in por_ano if l["ano"] == 2023 and l["secretaria"] == "SECA")
    assert linha_2023_seca["pct_do_total_ano"] == 25.0  # 100 / (100+300)
    linha_2024 = next(l for l in por_ano if l["ano"] == 2024)
    assert linha_2024["pct_do_total_ano"] == 100.0


def test_cartao_campo_preenchido_e_maior_secretaria() -> None:
    planos = [
        _plano(1, id_programa=1, firmado=600.0),
        _plano(2, id_programa=999, firmado=400.0),  # sem secretaria
    ]
    prog = [_programa(1, secretaria="SECA")]
    fato = montar_fato(planos, prog, resumo=[])
    _, nomes = montar_secretaria_e_nomes(prog)
    barras = montar_barras(fato, nomes)

    [cartao] = montar_cartao(fato, barras)

    assert cartao["firmado_total"] == 1000.0
    assert cartao["n_teds"] == 2
    assert cartao["maior_secretaria"] == "SECA"
    assert cartao["firmado_maior_secretaria"] == 600.0
    assert cartao["n_secretarias"] == 1
    assert cartao["pct_campo_preenchido"] == 50.0


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i4_devolve_quatro_saidas_e_passa_nas_checagens() -> None:
    planos = [
        _plano(1, id_programa=1, ano=2023, firmado=1000.0),
        _plano(2, id_programa=2, ano=2024, firmado=2000.0),
        _plano(3, situacao="REJEITADO"),
    ]
    prog = [_programa(1, secretaria="SECA"), _programa(2, secretaria="SECB")]
    resumo = [_resumo(1, "Emenda - X"), _resumo(2, "Recurso Próprio")]

    saidas = calcular_i4(planos, prog, resumo)

    assert set(saidas) == {
        "i4_ted_secretaria_fato", "i4_ted_secretaria_barras",
        "i4_ted_secretaria_por_ano", "i4_ted_secretaria_cartao",
    }
    assert len(saidas["i4_ted_secretaria_fato"]) == 2  # REJEITADO fora

    [cartao] = saidas["i4_ted_secretaria_cartao"]
    assert cartao["firmado_total"] == 3000.0
    assert cartao["n_teds"] == 2
