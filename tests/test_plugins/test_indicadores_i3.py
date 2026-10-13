"""Testes do indicador I3 — Público-Alvo por Grupo.

Cada teste cobre uma decisão metodológica do pacote Bloco 1 da equipe de BI
(``i3_ted_bi.R`` / ``i3_convenios_bi.R``), documentada no módulo
``plugins/indicadores/i3_publico_alvo.py``.
"""

from indicadores.i3_publico_alvo import (
    calcular_i3,
    calcular_i3_convenios,
    calcular_i3_ted,
    calcular_origem_por_plano,
    classificar,
    montar_barras,
    montar_cartao,
    montar_fato,
    montar_instrumentos_convenio,
    montar_instrumentos_ted,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _plano(id_plano_acao, situacao="APROVADO", ano=2024, **extra):
    base = {
        "id_plano_acao": id_plano_acao,
        "tx_situacao_plano_acao": situacao,
        "aa_ano_plano_acao": ano,
        "tx_objeto_plano_acao": "",
        "tx_justificativa_plano_acao": "",
    }
    base.update(extra)
    return base


def _resumo(plano_acao, origem):
    return {"plano_acao": plano_acao, "origem": origem}


def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              parlamentares=None, objeto="", empenhado=1000.0, pago=500.0,
              firmado_atualizado=1000.0, firmado_inicial=0.0, modalidade="CONVENIO"):
    return {
        "nr_convenio": nr,
        "modalidade_instrumento": modalidade,
        "parlamentares": parlamentares,
        "data_assinatura": assinatura,
        "inicio_vigencia": vigencia,
        "situacao_atual": situacao,
        "objeto": objeto,
        "valor_firmado_atualizado": firmado_atualizado,
        "valor_firmado_inicial": firmado_inicial,
        "valor_empenhado": empenhado,
        "valor_total_pago": pago,
    }


# ---------------------------------------------------------------------------
# classificar() — uma categoria por vez, com texto sintético
# ---------------------------------------------------------------------------
def test_classificar_pessoas_negras() -> None:
    cats = classificar("Atendimento a jovens negros em situação de vulnerabilidade")

    assert cats["pessoas_negras"] == 1
    assert cats["grupo_nomeado"] == 1


def test_classificar_quilombolas() -> None:
    assert classificar("Apoio a comunidades quilombolas")["quilombolas"] == 1


def test_classificar_indigenas_com_acento_e_maiuscula() -> None:
    assert classificar("Projeto para Povos INDÍGENAS do Norte")["indigenas"] == 1


def test_classificar_terreiro() -> None:
    assert classificar("Comunidades de terreiro e matriz africana")["terreiro"] == 1


def test_classificar_ciganos() -> None:
    """Categoria confirmada nos dados reais da BI, não marginal."""
    assert classificar("Atuação da SQPT junto a povos ciganos")["ciganos"] == 1


def test_classificar_generico_nao_conta_como_grupo_nomeado() -> None:
    cats = classificar("Promoção da igualdade racial no serviço público")

    assert cats["generico"] == 1
    assert cats["grupo_nomeado"] == 0
    assert cats["explicita_publico_racial"] == 1


def test_classificar_sem_mencao_racial() -> None:
    cats = classificar("Modernização de infraestrutura rodoviária")

    assert cats["grupo_nomeado"] == 0
    assert cats["explicita_publico_racial"] == 0


def test_classificar_mulheres_e_estudantes_negros_contam_em_pessoas_negras() -> None:
    """Não há subcategoria própria — conta só em pessoas_negras."""
    cats = classificar("Programa de bolsas para estudantes negros e mulheres negras")

    assert cats["pessoas_negras"] == 1
    assert cats["grupo_nomeado"] == 1
    assert set(cats) == {
        "pessoas_negras", "quilombolas", "indigenas", "terreiro", "ciganos",
        "generico", "grupo_nomeado", "explicita_publico_racial",
    }


def test_classificar_junta_varios_textos() -> None:
    cats = classificar("Objeto sem menção racial", "Justificativa cita quilombolas")

    assert cats["quilombolas"] == 1


# ---------------------------------------------------------------------------
# TED
# ---------------------------------------------------------------------------
def test_ted_rejeitado_fica_fora_do_universo() -> None:
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    instrumentos = montar_instrumentos_ted(planos, resumo=[])

    assert [i["id"] for i in instrumentos] == ["1"]


def test_ted_origem_vem_do_resumo_orcamentario() -> None:
    planos = [_plano(1)]
    resumo = [_resumo(1, "Emenda - Dep. X")]

    [instr] = montar_instrumentos_ted(planos, resumo)

    assert instr["origem"] == "Emenda"


def test_ted_origem_sem_informacao_quando_nao_bate_prefixo() -> None:
    origem = calcular_origem_por_plano([_resumo(1, "Tedinho (sem registro)")])

    assert origem["1"] == "Sem informação"


def test_ted_classifica_a_partir_de_objeto_e_justificativa() -> None:
    [instr] = montar_instrumentos_ted(
        [_plano(1, tx_objeto_plano_acao="Objeto neutro",
                tx_justificativa_plano_acao="Atendimento a quilombolas")],
        resumo=[],
    )

    assert instr["quilombolas"] == 1


# ---------------------------------------------------------------------------
# Convênios/Fomentos
# ---------------------------------------------------------------------------
def test_convenio_corte_temporal_2023() -> None:
    gold = [_convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01")]

    instrumentos = montar_instrumentos_convenio(gold)

    assert [i["id"] for i in instrumentos] == ["2"]


def test_convenio_exclui_situacao_sem_acento_e_caixa() -> None:
    gold = [
        _convenio(1, situacao="Cancelado"),
        _convenio(2, situacao="Convênio Anulado"),
        _convenio(3, situacao="Em execução"),
    ]

    instrumentos = montar_instrumentos_convenio(gold)

    assert [i["id"] for i in instrumentos] == ["3"]


def test_convenio_exclui_empenho_zero_com_pagamento_por_padrao() -> None:
    gold = [_convenio(1, empenhado=0.0, pago=100.0), _convenio(2, empenhado=100.0, pago=50.0)]

    instrumentos = montar_instrumentos_convenio(gold)

    assert [i["id"] for i in instrumentos] == ["2"]


def test_convenio_origem_emenda_quando_ha_parlamentar() -> None:
    gold = [_convenio(1, parlamentares="Deputado X"), _convenio(2, parlamentares="  ")]

    instrumentos = montar_instrumentos_convenio(gold)

    assert instrumentos[0]["origem"] == "Emenda"
    assert instrumentos[1]["origem"] == "Regular"


def test_convenio_classifica_pelo_objeto() -> None:
    [instr] = montar_instrumentos_convenio([_convenio(1, objeto="Apoio a povos indígenas")])

    assert instr["indigenas"] == 1
    assert instr["grupo_nomeado"] == 1
    assert instr["modalidade"] == "Convenio"
    assert instr["qualidade_dado"] == "ok"


# ---------------------------------------------------------------------------
# Fato / barras / cartão
# ---------------------------------------------------------------------------
def test_montar_fato_uma_linha_por_instrumento_e_grupo() -> None:
    instrumentos = montar_instrumentos_ted(
        [_plano(1, tx_objeto_plano_acao="Apoio a quilombolas")], resumo=[],
    )

    fato = montar_fato(instrumentos, dims=["ano", "origem"])

    assert len(fato) == 5  # 1 instrumento x 5 grupos
    ativos = {f["grupo"]: f["ativo"] for f in fato}
    assert ativos["Quilombolas"] == 1
    assert ativos["Ciganos"] == 0


def test_montar_barras_ordena_por_quantidade_desc_e_desempata_por_ordem_base() -> None:
    instrumentos = montar_instrumentos_ted(
        [
            _plano(1, tx_objeto_plano_acao="Apoio a quilombolas e povos indigenas"),
            _plano(2, tx_objeto_plano_acao="Apoio a quilombolas"),
        ],
        resumo=[],
    )
    fato = montar_fato(instrumentos, dims=["ano", "origem"])

    barras = montar_barras(fato, len(instrumentos))

    assert barras[0]["grupo"] == "Quilombolas"
    assert barras[0]["n_instrumentos"] == 2
    assert barras[0]["pct_do_total"] == 100.0
    assert barras[0]["ordem_exibicao"] == 1
    assert barras[1]["grupo"] == "Indígenas"
    assert barras[1]["n_instrumentos"] == 1


def test_montar_cartao_agrega_metricas_da_tela() -> None:
    instrumentos = montar_instrumentos_ted(
        [
            _plano(1, tx_objeto_plano_acao="Apoio a quilombolas"),
            _plano(2, tx_objeto_plano_acao="Promocao da igualdade racial"),
            _plano(3, tx_objeto_plano_acao="Sem mencao racial"),
        ],
        resumo=[],
    )
    fato = montar_fato(instrumentos, dims=["ano", "origem"])
    barras = montar_barras(fato, len(instrumentos))

    [cartao] = montar_cartao(instrumentos, barras)

    assert cartao["n_instrumentos"] == 3
    assert cartao["n_grupo_nomeado"] == 1
    assert cartao["n_explicitam_publico_racial"] == 2  # grupo nomeado OU genérico
    assert cartao["grupo_mais_citado"] == "Quilombolas"
    assert cartao["n_grupo_mais_citado"] == 1


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i3_ted_devolve_tres_saidas_e_passa_nas_checagens() -> None:
    planos = [
        _plano(1, tx_objeto_plano_acao="Apoio a quilombolas"),
        _plano(2, tx_objeto_plano_acao="Sem mencao racial"),
    ]

    saidas = calcular_i3_ted(planos, resumo=[])

    assert set(saidas) == {"i3_ted_publico_fato", "i3_ted_publico_barras", "i3_ted_publico_cartao"}
    assert len(saidas["i3_ted_publico_fato"]) == 10  # 2 instrumentos x 5 grupos
    assert len(saidas["i3_ted_publico_barras"]) == 5


def test_calcular_i3_convenios_devolve_tres_saidas_e_passa_nas_checagens() -> None:
    gold = [
        _convenio(1, objeto="Apoio a povos indigenas"),
        _convenio(2, objeto="Sem mencao racial"),
    ]

    saidas = calcular_i3_convenios(gold)

    assert set(saidas) == {
        "i3_convenio_publico_fato", "i3_convenio_publico_barras", "i3_convenio_publico_cartao",
    }
    assert len(saidas["i3_convenio_publico_fato"]) == 10
    assert len(saidas["i3_convenio_publico_barras"]) == 5


def test_calcular_i3_devolve_as_seis_saidas() -> None:
    saidas = calcular_i3(
        planos=[_plano(1, tx_objeto_plano_acao="Apoio a quilombolas")],
        resumo=[],
        gold_convenios=[_convenio(1, objeto="Sem mencao racial")],
    )

    assert set(saidas) == {
        "i3_ted_publico_fato", "i3_ted_publico_barras", "i3_ted_publico_cartao",
        "i3_convenio_publico_fato", "i3_convenio_publico_barras", "i3_convenio_publico_cartao",
    }
