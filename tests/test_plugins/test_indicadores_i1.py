"""Testes do indicador I1 — Valor Executado por Instrumento.

Cada teste cobre uma decisão metodológica do pacote Bloco 1 da equipe de BI
(``i1_ted_bi.R`` / ``i1_convenios_bi.R``), documentada no módulo
``plugins/indicadores/i1_valor_executado.py``.
"""

import pytest

from indicadores.i1_valor_executado import (
    agregar_convenio_por_ano,
    agregar_convenio_por_origem,
    agregar_execucao_ano,
    agregar_fato_ano,
    agregar_qualidade,
    agregar_safra_origem,
    agregar_ted_por_ano,
    agregar_ted_por_origem,
    calcular_cartoes_convenio,
    calcular_cartoes_ted,
    calcular_execucao_por_plano_ano,
    calcular_i1,
    calcular_i1_convenios,
    calcular_i1_ted,
    calcular_origem_por_plano,
    montar_instrumentos_convenio,
    montar_instrumentos_ted,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _plano(id_plano_acao, situacao="APROVADO", ano=2024, firmado=1000.0):
    return {
        "id_plano_acao": id_plano_acao,
        "tx_situacao_plano_acao": situacao,
        "aa_ano_plano_acao": ano,
        "vl_total_plano_acao": firmado,
    }


def _empenho(plano_acao, empenhado=0, liquidado=0, pago=0, rap_insc=0, rap_pago=0, ano_emissao=2024):
    return {
        "plano_acao": plano_acao,
        "despesas_empenhadas": empenhado,
        "despesas_liquidadas": liquidado,
        "despesas_pagas": pago,
        "restos_a_pagar_inscritos": rap_insc,
        "restos_a_pagar_pagos": rap_pago,
        "ne_ccor_ano_emissao": ano_emissao,
    }


def _resumo(plano_acao, origem):
    return {"plano_acao": plano_acao, "origem": origem}


def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              parlamentares=None, firmado_atualizado=1000.0, firmado_inicial=0.0,
              empenhado=1000.0, pago=500.0, modalidade="CONVENIO"):
    return {
        "nr_convenio": nr,
        "modalidade_instrumento": modalidade,
        "parlamentares": parlamentares,
        "data_assinatura": assinatura,
        "inicio_vigencia": vigencia,
        "situacao_atual": situacao,
        "valor_firmado_atualizado": firmado_atualizado,
        "valor_firmado_inicial": firmado_inicial,
        "valor_empenhado": empenhado,
        "valor_total_pago": pago,
    }


# ---------------------------------------------------------------------------
# TED
# ---------------------------------------------------------------------------
def test_ted_rejeitado_fica_fora() -> None:
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    inst = montar_instrumentos_ted(planos, [], [])

    assert [i["id_plano_acao"] for i in inst] == ["1"]


def test_ted_dedup_mantem_primeira_ocorrencia() -> None:
    planos = [_plano(1, firmado=100.0), _plano(1, firmado=999.0)]

    inst = montar_instrumentos_ted(planos, [], [])

    assert len(inst) == 1
    assert inst[0]["firmado"] == 100.0


def test_ted_origem_emenda() -> None:
    origem = calcular_origem_por_plano([_resumo(1, "Emenda - Dep. X")])

    assert origem["1"] == "Emenda"


def test_ted_origem_regular() -> None:
    origem = calcular_origem_por_plano([_resumo(1, "Recurso Próprio")])

    assert origem["1"] == "Regular"


def test_ted_origem_sem_informacao_quando_nao_bate_nenhum_prefixo() -> None:
    origem = calcular_origem_por_plano([_resumo(1, "Tedinho (sem registro no TransfereGov)")])

    assert origem["1"] == "Sem informação"


def test_ted_origem_sem_informacao_quando_plano_sem_linha_no_resumo() -> None:
    inst = montar_instrumentos_ted([_plano(1)], [], [])

    assert inst[0]["origem"] == "Sem informação"


def test_ted_empenhado_soma_varias_notas_e_ja_vem_liquido() -> None:
    """despesas_empenhadas já tem o sinal da anulação embutido (negativo = anulação)."""
    empenhos = [_empenho(1, empenhado=1000.0), _empenho(1, empenhado=-50.0)]

    inst = montar_instrumentos_ted([_plano(1)], empenhos, [])

    assert inst[0]["empenhado"] == 950.0


def test_ted_pago_nao_soma_rap() -> None:
    empenhos = [_empenho(1, pago=100.0, rap_pago=50.0)]

    inst = montar_instrumentos_ted([_plano(1)], empenhos, [])

    assert inst[0]["pago"] == 100.0
    assert inst[0]["rap_pagos"] == 50.0


def test_ted_sem_empenho_flag() -> None:
    planos = [_plano(1), _plano(2)]
    empenhos = [_empenho(1, empenhado=500.0)]

    inst = montar_instrumentos_ted(planos, empenhos, [])

    por_id = {i["id_plano_acao"]: i["sem_empenho"] for i in inst}
    assert por_id["1"] == 0
    assert por_id["2"] == 1


def test_ted_pct_do_firmado_total() -> None:
    planos = [_plano(1, ano=2023, firmado=300.0), _plano(2, ano=2024, firmado=700.0)]
    inst = montar_instrumentos_ted(planos, [], [])

    por_ano = agregar_ted_por_ano(inst)

    pct = {l["ano"]: l["pct_do_firmado_total"] for l in por_ano}
    assert pct[2023] == 30.0
    assert pct[2024] == 70.0


def test_ted_execucao_por_ano_usa_ano_de_emissao_da_nota() -> None:
    """Eixo "ano de execução" é separado do ano de assinatura do plano."""
    planos = [_plano(1, ano=2023)]
    empenhos = [
        _empenho(1, empenhado=100.0, ano_emissao=2023),
        _empenho(1, empenhado=200.0, ano_emissao=2024),
    ]

    inst = montar_instrumentos_ted(planos, empenhos, [])
    exec_ano = calcular_execucao_por_plano_ano(empenhos)
    saida = agregar_execucao_ano(inst, exec_ano)

    por_ano = {l["ano_execucao"]: l["empenhado"] for l in saida}
    assert por_ano == {2023: 100.0, 2024: 200.0}


def test_calcular_i1_ted_devolve_seis_saidas_e_passa_nas_checagens() -> None:
    planos = [
        _plano(1, ano=2023, firmado=1000.0),
        _plano(2, ano=2024, firmado=2000.0),
        _plano(3, situacao="REJEITADO"),
    ]
    empenhos = [
        _empenho(1, empenhado=500.0, liquidado=400.0, pago=300.0, ano_emissao=2023),
        _empenho(2, empenhado=1000.0, liquidado=900.0, pago=800.0, ano_emissao=2024),
        _empenho(2, empenhado=200.0, liquidado=100.0, pago=50.0, ano_emissao=2025),
        _empenho(99, empenhado=10_000.0),  # plano fora do universo (nem existe em planos)
    ]
    resumo = [_resumo(1, "Emenda - X"), _resumo(2, "Recurso Próprio")]

    saidas = calcular_i1_ted(planos, empenhos, resumo)

    assert set(saidas) == {
        "i1_ted_cartoes", "i1_ted_safra_origem", "i1_ted_execucao_ano",
        "i1_ted_por_ano", "i1_ted_por_origem", "i1_ted_instrumentos",
    }
    assert len(saidas["i1_ted_instrumentos"]) == 2  # REJEITADO fora

    cartoes = {c["etapa"]: c["valor"] for c in saidas["i1_ted_cartoes"]}
    assert cartoes["Firmado"] == 3000.0
    assert cartoes["Empenhado"] == 1700.0
    assert cartoes["Pago"] == 1150.0

    # plano 99 (fora do universo) não pode contaminar o total de execução por ano
    assert sum(l["empenhado"] for l in saidas["i1_ted_execucao_ano"]) == 1700.0


# ---------------------------------------------------------------------------
# Convênios/Fomentos
# ---------------------------------------------------------------------------
def test_convenio_corte_temporal_2023() -> None:
    gold = [_convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01")]

    inst, _ = montar_instrumentos_convenio(gold)

    assert [i["nr_convenio"] for i in inst] == ["2"]


def test_convenio_exclui_situacao_sem_acento_e_caixa() -> None:
    gold = [
        _convenio(1, situacao="Cancelado"),
        _convenio(2, situacao="CANCELADO"),
        _convenio(3, situacao="Convênio Anulado"),
        _convenio(4, situacao="convenio anulado"),
        _convenio(5, situacao="Em execução"),
    ]

    inst, _ = montar_instrumentos_convenio(gold)

    assert [i["nr_convenio"] for i in inst] == ["5"]


def test_convenio_firmado_cai_para_inicial_quando_atualizado_nao_positivo() -> None:
    gold = [_convenio(1, firmado_atualizado=0.0, firmado_inicial=777.0)]

    inst, _ = montar_instrumentos_convenio(gold)

    assert inst[0]["firmado"] == 777.0


def test_convenio_qualidade_empenho_zero_com_pagamento_e_excluido_por_padrao() -> None:
    gold = [_convenio(1, empenhado=0.0, pago=100.0)]

    inst, excluidos = montar_instrumentos_convenio(gold)

    assert len(inst) == 0
    assert len(excluidos) == 1
    assert excluidos[0]["qualidade_dado"] == "empenho_zero_com_pagamento"


def test_convenio_qualidade_pago_maior_que_empenhado() -> None:
    gold = [_convenio(1, empenhado=100.0, pago=150.0)]

    inst, _ = montar_instrumentos_convenio(gold)

    assert inst[0]["qualidade_dado"] == "pago_maior_que_empenhado"


def test_convenio_qualidade_sem_empenho() -> None:
    gold = [_convenio(1, empenhado=0.0, pago=0.0)]

    inst, _ = montar_instrumentos_convenio(gold)

    assert inst[0]["qualidade_dado"] == "sem_empenho"


def test_convenio_qualidade_empenho_parcial() -> None:
    gold = [_convenio(1, firmado_atualizado=1000.0, empenhado=400.0, pago=100.0)]

    inst, _ = montar_instrumentos_convenio(gold)

    assert inst[0]["qualidade_dado"] == "empenho_parcial"


def test_convenio_qualidade_ok() -> None:
    gold = [_convenio(1, firmado_atualizado=1000.0, empenhado=1000.0, pago=500.0)]

    inst, _ = montar_instrumentos_convenio(gold)

    assert inst[0]["qualidade_dado"] == "ok"


def test_convenio_origem_emenda_quando_parlamentar_preenchido() -> None:
    gold = [_convenio(1, parlamentares="Dep. X"), _convenio(2, parlamentares="  ")]

    inst, _ = montar_instrumentos_convenio(gold)

    origem = {i["nr_convenio"]: i["origem"] for i in inst}
    assert origem == {"1": "Emenda", "2": "Regular"}


def test_calcular_i1_convenios_devolve_sete_saidas_e_bate_checagens() -> None:
    gold = [
        _convenio(1, firmado_atualizado=1000.0, empenhado=1000.0, pago=500.0),
        _convenio(2, firmado_atualizado=2000.0, empenhado=0.0, pago=0.0),
        _convenio(3, empenhado=0.0, pago=50.0),  # excluído (empenho_zero_com_pagamento)
        _convenio(4, assinatura="2020-01-01"),   # fora do corte
    ]

    saidas = calcular_i1_convenios(gold)

    assert set(saidas) == {
        "i1_convenio_cartoes", "i1_convenio_fato_ano", "i1_convenio_por_ano",
        "i1_convenio_por_origem", "i1_convenio_instrumentos", "i1_convenio_qualidade",
        "i1_convenio_excluidos",
    }
    assert len(saidas["i1_convenio_instrumentos"]) == 2
    assert len(saidas["i1_convenio_excluidos"]) == 1

    cartoes = {c["etapa"]: c["valor"] for c in saidas["i1_convenio_cartoes"]}
    assert cartoes["Firmado"] == 3000.0


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i1_devolve_as_treze_saidas() -> None:
    saidas = calcular_i1(
        planos=[_plano(1)],
        empenhos=[_empenho(1, empenhado=500.0)],
        resumo=[_resumo(1, "Recurso Próprio")],
        gold_convenios=[_convenio(1)],
    )

    assert set(saidas) == {
        "i1_ted_cartoes", "i1_ted_safra_origem", "i1_ted_execucao_ano",
        "i1_ted_por_ano", "i1_ted_por_origem", "i1_ted_instrumentos",
        "i1_convenio_cartoes", "i1_convenio_fato_ano", "i1_convenio_por_ano",
        "i1_convenio_por_origem", "i1_convenio_instrumentos", "i1_convenio_qualidade",
        "i1_convenio_excluidos",
    }
