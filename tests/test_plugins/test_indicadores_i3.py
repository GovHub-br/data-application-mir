"""Testes do indicador I3 — Instrumentos com Público-Alvo Racializado.

Cada teste unitário cobre uma decisão metodológica registrada no script
original da equipe de BI (i3_publico_alvo.py).
As entradas têm o formato das tabelas dos marts mir_teds e mir_convenios.

AVISO: diferente do I1 e do I2, não há fixture de regressão ponta-a-ponta
contra dado bruto real — os textos de objeto/justificativa que alimentam a
classificação não estavam disponíveis no ambiente de porte (só os CSVs de
saída já processados pela BI, sem o texto de entrada). Os testes de
`classificar()` usam texto sintético que exercita cada padrão de regex. Os
testes de regressão em `montar_grupos_ted`/`montar_grupos_convenio` são
reais: "despivotam" o CSV de saída real da BI de volta pro formato largo e
conferem que a função reproduz exatamente o CSV original — validam a
mecânica do unpivot, não a classificação de texto em si.
"""

import csv
from pathlib import Path

import pytest

from indicadores.i3_publico_alvo import (
    calcular_i3,
    calcular_resumo,
    classificar,
    montar_grupos_convenio,
    montar_grupos_ted,
    montar_instrumentos_convenio,
    montar_instrumentos_ted,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "indicadores" / "i3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sk(id_plano_acao):
    """Chave do plano diferente do número (como o hash dos marts); -1 é o membro -1."""
    return -1 if id_plano_acao == -1 else 10_000 + id_plano_acao


def _plano(id_plano_acao, situacao="APROVADO", **extra):
    """Linha de mir_teds.dim_plano_acao."""
    base = {
        "sk_plano_acao": _sk(id_plano_acao),
        "id_plano_acao": id_plano_acao,
        "situacao": situacao,
        "ano": 2024,
        "sigla_unidade_descentralizada": "UFX",
        "origem_recurso": "Recurso próprio",
        "objeto": "",
        "justificativa": "",
    }
    base.update(extra)
    return base


def _nc(id_plano_acao, ptres):
    """Linha de mir_teds.fato_credito_descentralizado (só as colunas usadas)."""
    return {"sk_plano_acao": _sk(id_plano_acao), "ptres": ptres}


def _acao(ptres, codigo_programa):
    """Linha de mir_teds.dim_acao_orcamentaria (só as colunas usadas)."""
    return {"ptres": ptres, "codigo_programa": codigo_programa}


def _convenio(nr, assinatura="2024-03-01", vigencia=None, situacao="Em execução",
              origem="Recurso próprio", objeto="", **extra):
    """Um convênio com os campos de dim_convenio e o nome do convenente."""
    base = {
        "nr_convenio": nr,
        "modalidade": "CONVENIO",
        "origem_recurso": origem,
        "data_assinatura": assinatura,
        "data_inicio_vigencia": vigencia,
        "situacao": situacao,
        "objeto": objeto,
        "convenente_nome": "Prefeitura",
    }
    base.update(extra)
    return base


def _fontes_convenios(especificacoes):
    """Separa os convênios em dim_convenio, posição e dim_convenente, ligados por sk."""
    fontes = {"convenios": [], "posicao_convenios": [], "convenentes": []}
    for i, c in enumerate(especificacoes, start=1):
        fontes["convenios"].append({
            "sk_convenio": i,
            **{k: v for k, v in c.items() if k != "convenente_nome"},
        })
        fontes["posicao_convenios"].append({"sk_convenio": i, "sk_convenente": 100 + i})
        fontes["convenentes"].append(
            {"sk_convenente": 100 + i, "convenente_nome": c["convenente_nome"]}
        )
    return fontes


# ---------------------------------------------------------------------------
# classificar() — uma categoria por vez, com texto sintético
# ---------------------------------------------------------------------------
def test_classificar_pessoas_negras() -> None:
    cats = classificar("Atendimento a jovens negros em situação de vulnerabilidade")
    assert cats["pessoas_negras"] == 1
    assert cats["leitura_estrita"] == 1


def test_classificar_quilombolas() -> None:
    assert classificar("Apoio a comunidades quilombolas")["quilombolas"] == 1


def test_classificar_indigenas_com_acento_e_maiuscula() -> None:
    """normalizar() precisa lidar com acento e caixa antes do regex."""
    assert classificar("Projeto para Povos INDÍGENAS do Norte")["indigenas"] == 1


def test_classificar_terreiro() -> None:
    assert classificar("Comunidades de terreiro e matriz africana")["terreiro"] == 1


def test_classificar_ciganos() -> None:
    """Decisão 1: categoria não marginal, confirmada nos dados reais da BI."""
    assert classificar("Atuação da SQPT junto a povos ciganos")["ciganos"] == 1


def test_classificar_racial_generico_nao_conta_como_leitura_estrita() -> None:
    """Decisão 2: racial_generico sozinho não ativa leitura_estrita, só ampla."""
    cats = classificar("Promoção da igualdade racial no serviço público")

    assert cats["racial_generico"] == 1
    assert cats["leitura_estrita"] == 0
    assert cats["leitura_ampla"] == 1


def test_classificar_sem_mencao_racial() -> None:
    cats = classificar("Modernização de infraestrutura rodoviária")

    assert cats["leitura_estrita"] == 0
    assert cats["leitura_ampla"] == 0


def test_classificar_subcategorias_nao_alteram_leitura_estrita() -> None:
    """Decisão 6: mulheres_negras/estudantes_negros são subconjunto, não categoria
    extra."""
    cats = classificar("Programa de bolsas para estudantes negros e mulheres negras")

    assert cats["mulheres_negras"] == 1
    assert cats["estudantes_negros"] == 1
    assert cats["pessoas_negras"] == 1
    assert cats["leitura_estrita"] == 1


def test_classificar_junta_objeto_e_justificativa() -> None:
    cats = classificar("Objeto sem menção racial", "Justificativa cita quilombolas")

    assert cats["quilombolas"] == 1


# ---------------------------------------------------------------------------
# Bloco 1 — TED: universo e campos
# ---------------------------------------------------------------------------
def test_ted_rejeitado_fica_fora_do_universo() -> None:
    """Decisão 4: mesmo filtro de situação do I1."""
    planos = [_plano(1), _plano(2, situacao="REJEITADO")]

    instrumentos = montar_instrumentos_ted(planos, creditos_teds=[], acoes_teds=[])

    assert [i["id_instrumento"] for i in instrumentos] == ["1"]


def test_ted_membro_nao_identificado_fica_fora() -> None:
    planos = [_plano(1), _plano(-1, situacao="Não identificado")]

    instrumentos = montar_instrumentos_ted(planos, [], [])

    assert [i["id_instrumento"] for i in instrumentos] == ["1"]


def test_ted_origem_emenda_pela_origem_recurso() -> None:
    planos = [_plano(1, origem_recurso="Emenda"), _plano(2)]

    instrumentos = montar_instrumentos_ted(planos, [], [])

    assert {i["id_instrumento"]: i["origem"] for i in instrumentos} == {
        "1": "emenda",
        "2": "orcamento_regular",
    }


def test_ted_programa_governo_e_o_maior_programa_das_ncs() -> None:
    """Mesma regra do I1 (e do gold antigo): max(programa) das NCs do plano."""
    planos = [_plano(1), _plano(2)]
    acoes = [_acao("172001", "5802"), _acao("172002", "5804")]
    creditos = [_nc(1, "172001"), _nc(1, "172002")]

    instrumentos = montar_instrumentos_ted(planos, creditos, acoes)

    assert [i["programa_governo"] for i in instrumentos] == ["5804", ""]


def test_ted_classifica_objeto_e_justificativa() -> None:
    planos = [_plano(1, objeto="Formação", justificativa="Comunidades quilombolas")]

    [instr] = montar_instrumentos_ted(planos, [], [])

    assert instr["quilombolas"] == 1


def test_ted_tx_objeto_truncado_em_200_caracteres() -> None:
    planos = [_plano(1, objeto="x" * 300)]

    [instr] = montar_instrumentos_ted(planos, [], [])

    assert len(instr["tx_objeto"]) == 200


def test_ted_tipo_e_instrumento_sempre_ted() -> None:
    [instr] = montar_instrumentos_ted([_plano(1)], [], [])

    assert instr["tipo"] == "TED"
    assert instr["instrumento"] == "TED"
    assert instr["ano"] == "2024"
    assert instr["sigla_executor"] == "UFX"
    assert instr["programa_governo"] == ""  # sem NC


# ---------------------------------------------------------------------------
# Bloco 2 — Convênios: universo e campos (mesmo do I1)
# ---------------------------------------------------------------------------
def test_convenio_corte_temporal_2023() -> None:
    fontes = _fontes_convenios([
        _convenio(1, assinatura="2022-12-31"), _convenio(2, assinatura="2023-01-01"),
    ])

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["id_instrumento"] for i in instrumentos] == ["2"]


def test_convenio_ano_fallback_para_inicio_vigencia() -> None:
    fontes = _fontes_convenios([_convenio(1, assinatura=None, vigencia="2024-05-10")])

    [instr] = montar_instrumentos_convenio(**fontes)

    assert instr["ano"] == 2024


def test_convenio_exclui_cancelado_e_anulado() -> None:
    fontes = _fontes_convenios([
        _convenio(1, situacao="Cancelado"),
        _convenio(2, situacao="Convênio Anulado"),
        _convenio(3, situacao="Em execução"),
    ])

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["id_instrumento"] for i in instrumentos] == ["3"]


def test_convenio_origem_emenda_pela_origem_recurso() -> None:
    fontes = _fontes_convenios([
        _convenio(1, origem="Emenda"), _convenio(2, origem="Não identificada"),
    ])

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["origem"] for i in instrumentos] == ["emenda", "orcamento_regular"]


def test_convenio_sem_programa_governo_decisao_5() -> None:
    [instr] = montar_instrumentos_convenio(**_fontes_convenios([_convenio(1)]))

    assert instr["programa_governo"] == ""
    assert instr["tipo"] == "Convenio_Fomento"
    assert instr["instrumento"] == "CONVENIO"
    assert instr["sigla_executor"] == "Prefeitura"


def test_convenio_membro_nao_identificado_fica_fora() -> None:
    fontes = _fontes_convenios([_convenio(1)])
    fontes["convenios"].append({
        "sk_convenio": -1, "nr_convenio": "-1", "modalidade": "Não identificado",
        "origem_recurso": "Não identificada", "situacao": "Não identificado",
        "data_assinatura": "2024-01-01", "data_inicio_vigencia": None, "objeto": None,
    })

    instrumentos = montar_instrumentos_convenio(**fontes)

    assert [i["id_instrumento"] for i in instrumentos] == ["1"]


def test_convenio_classifica_pelo_objeto() -> None:
    fontes = _fontes_convenios([_convenio(1, objeto="Apoio a povos indígenas")])

    [instr] = montar_instrumentos_convenio(**fontes)

    assert instr["indigenas"] == 1
    assert instr["leitura_estrita"] == 1


# ---------------------------------------------------------------------------
# Resumo por bloco
# ---------------------------------------------------------------------------
def test_resumo_calcula_estrita_ampla_e_gap() -> None:
    instrumentos = [
        {"tipo": "TED", "instrumento": "TED", "leitura_estrita": 1, "leitura_ampla": 1,
         "racial_generico": 0, "pessoas_negras": 1, "mulheres_negras": 0,
         "estudantes_negros": 0, "quilombolas": 0, "indigenas": 0, "terreiro": 0,
         "ciganos": 0},
        {"tipo": "TED", "instrumento": "TED", "leitura_estrita": 0, "leitura_ampla": 1,
         "racial_generico": 1, "pessoas_negras": 0, "mulheres_negras": 0,
         "estudantes_negros": 0, "quilombolas": 0, "indigenas": 0, "terreiro": 0,
         "ciganos": 0},
        {"tipo": "TED", "instrumento": "TED", "leitura_estrita": 0, "leitura_ampla": 0,
         "racial_generico": 0, "pessoas_negras": 0, "mulheres_negras": 0,
         "estudantes_negros": 0, "quilombolas": 0, "indigenas": 0, "terreiro": 0,
         "ciganos": 0},
    ]

    [ted, conv, total] = calcular_resumo(instrumentos)

    assert ted["total_instrumentos"] == 3
    assert ted["leitura_estrita_pct"] == pytest.approx(33.3, abs=0.1)
    assert ted["leitura_ampla_pct"] == pytest.approx(66.7, abs=0.1)
    assert ted["gap_leitura_pct"] == pytest.approx(33.3, abs=0.1)
    assert ted["racial_generico_apenas"] == 1
    assert ted["sem_mencao_racial"] == 1
    assert conv["total_instrumentos"] == 0
    assert total["total_instrumentos"] == 3


def test_resumo_por_modalidade_exclui_ted_ja_coberto() -> None:
    instrumentos = [
        {"tipo": "Convenio_Fomento", "instrumento": "TERMO DE FOMENTO",
         "leitura_estrita": 1, "leitura_ampla": 1, "racial_generico": 0,
         "pessoas_negras": 1, "mulheres_negras": 0, "estudantes_negros": 0,
         "quilombolas": 0, "indigenas": 0, "terreiro": 0, "ciganos": 0},
    ]

    linhas = calcular_resumo(instrumentos)
    tipos = [l["tipo"] for l in linhas]

    assert "TERMO DE FOMENTO" in tipos
    assert tipos.count("TED") == 1  # a linha-resumo fixa, não duplicada por modalidade


# ---------------------------------------------------------------------------
# Formato longo — regressão real (unpivot da saída real da BI)
# ---------------------------------------------------------------------------
INT_COLS = {"ativo", "leitura_estrita", "leitura_ampla", "racial_generico"}


def _ler_grupos(nome):
    with open(FIXTURES / nome, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _despivotar(linhas_longas, id_campo, campo_extra):
    """Reconstrói o formato largo (um instrumento por linha) a partir do
    formato longo (uma linha por grupo) — usado só para alimentar a função
    de unpivot de volta e conferir que ela reproduz o CSV original."""
    largo: dict[str, dict] = {}
    for l in linhas_longas:
        rid = l[id_campo]
        if rid not in largo:
            largo[rid] = {
                "id_instrumento": rid,
                "leitura_estrita": int(l["leitura_estrita"]),
                "leitura_ampla": int(l["leitura_ampla"]),
                "racial_generico": int(l["racial_generico"]),
                campo_extra: l[campo_extra],
                "origem": l["origem"],
                "ano": l["ano"],
            }
        largo[rid][l["grupo"]] = int(l["ativo"])
    return list(largo.values())


def test_regressao_montar_grupos_ted_reproduz_saida_real_da_bi() -> None:
    real = _ler_grupos("i3_ted_publico_alvo_grupos.csv")
    instrumentos = _despivotar(real, "id_plano_acao", "programa_governo")

    resultado = montar_grupos_ted(instrumentos)

    esperado = [
        {k: (int(v) if k in INT_COLS else v) for k, v in linha.items()} for linha in real
    ]
    assert resultado == esperado


def test_regressao_montar_grupos_convenio_reproduz_saida_real_da_bi() -> None:
    real = _ler_grupos("i3_convenio_publico_alvo_grupos.csv")
    instrumentos = _despivotar(real, "nr_convenio", "instrumento")

    resultado = montar_grupos_convenio(instrumentos)

    esperado = [
        {k: (int(v) if k in INT_COLS else v) for k, v in linha.items()} for linha in real
    ]
    assert resultado == esperado


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def test_calcular_i3_devolve_as_quatro_saidas() -> None:
    saidas = calcular_i3(
        planos=[_plano(1, objeto="Apoio a quilombolas")],
        creditos_teds=[],
        acoes_teds=[],
        **_fontes_convenios([_convenio(1, objeto="Sem menção racial")]),
    )

    assert set(saidas) == {
        "i3_publico_alvo_instrumentos",
        "i3_publico_alvo_resumo",
        "i3_ted_publico_alvo_grupos",
        "i3_convenio_publico_alvo_grupos",
    }
    assert len(saidas["i3_publico_alvo_instrumentos"]) == 2
    assert len(saidas["i3_ted_publico_alvo_grupos"]) == 5
    assert len(saidas["i3_convenio_publico_alvo_grupos"]) == 5
