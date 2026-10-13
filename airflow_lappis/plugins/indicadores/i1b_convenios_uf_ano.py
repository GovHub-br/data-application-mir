"""Indicador I1b — Taxa de Execução por UF e Ano (Convênios/Fomentos).

Porte de ``I1/i1b_convenios_uf_ano_bi.R`` (equipe de BI, pacote Bloco 1).
Indicador NOVO — existe só para convênios/fomentos (o TED não tem
território na base). É a única tela do pacote que reporta uma TAXA; as
demais entregam só valores brutos.

Mapa de calor: linhas = 8 maiores UFs por firmado + "Demais" (as outras
somadas); colunas = ano de assinatura; célula = pago ÷ firmado do grupo
(nunca a média das taxas individuais) e nº de convênios.

UNIVERSO E VALORES: idênticos ao i1_convenios_bi.R (mesma fonte
gold_convenios, mesmo corte de ano, mesmas situações excluídas, mesma
exclusão de ``empenho_zero_com_pagamento`` e mesma coluna
``qualidade_dado``) — para que os totais por ano batam com a tela do I1
(``PR #85``).

COMO A UF É DEFINIDA (coluna ``fonte_uf``):
 1. "meta" — UF da(s) meta(s) física(s) do instrumento em
    ``convenio_meta_crono_fisico`` (``uf_meta``): onde a execução está
    prevista de fato.
 2. "sede" — quando o instrumento não tem ``uf_meta``, usa ``uf_execucao``
    do gold_convenios — na prática a sede do convenente, NÃO comprova onde
    o recurso foi aplicado. Essa coluna está em branco desde o fix de
    ``siconv_dbt.resumo_convenios`` (``PR #80`` — decisão da equipe: dado
    real virá do coleta mir), então hoje esse ramo nunca é alcançado.
 Metas em mais de uma UF: linha "Múltiplas UFs" (valor não é repartido,
 não há base para isso). Sem nenhuma das duas informações: "Sem UF".

LINHA "DEMAIS": as N_UFS_DESTAQUE maiores UFs por firmado total (todos os
anos) aparecem individualmente; as demais somadas em "Demais". Ranking
recalculado a cada execução.

Fontes (tabelas dbt):
    siconv_dbt.resumo_convenios            → gold_convenios
    siconv_dbt.convenio_meta_crono_fisico  → metas físicas (UF real, quando há)

Saídas (3):
    i1b_convenio_uf_ano_fato  — fato: uf x uf_grupo x ano x origem x modalidade
                                 x qualidade_dado
    i1b_convenio_heatmap      — uf_grupo x ano (grade completa), com taxa de execução
    i1b_convenio_cartoes_ano  — totais por ano (firmado, pago, taxa)
"""

import unicodedata
from collections import defaultdict
from datetime import date, datetime
from typing import Any

ANO_CORTE = 2023
SITUACOES_EXCLUIDAS = {"cancelado", "convenio anulado"}
EXCLUIR_EMPENHO_ZERO_COM_PAGO = True
ROTULO_EMENDA = "Emenda"
ROTULO_REGULAR = "Regular"
N_UFS_DESTAQUE = 8
ROTULO_DEMAIS = "Demais"
ROTULO_MULTIPLAS = "Múltiplas UFs"
ROTULO_SEM_UF = "Sem UF"


# ---------------------------------------------------------------------------
# Normalização (mesmos helpers do i1_valor_executado.py)
# ---------------------------------------------------------------------------
def _txt(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _num(valor: Any) -> float:
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return 0.0
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _ano_data(valor: Any) -> int | None:
    if isinstance(valor, (date, datetime)):
        return valor.year
    texto = _txt(valor)
    if len(texto) >= 4 and texto[:4].isdigit():
        return int(texto[:4])
    return None


def _ano_instrumento(data_assinatura: Any, inicio_vigencia: Any) -> int | None:
    return _ano_data(data_assinatura) or _ano_data(inicio_vigencia)


def _limpa_uf(valor: Any) -> str:
    texto = _txt(valor).upper()
    return texto if len(texto) == 2 and texto.isalpha() else ""


def _qualidade_dado(empenhado: float, pago: float, firmado: float) -> str:
    if empenhado == 0 and pago > 0:
        return "empenho_zero_com_pagamento"
    if pago > empenhado + 0.01:
        return "pago_maior_que_empenhado"
    if empenhado == 0:
        return "sem_empenho"
    if abs(firmado - empenhado) > 0.01:
        return "empenho_parcial"
    return "ok"


def _taxa(pago: float, firmado: float) -> float | None:
    return round(100 * pago / firmado, 1) if firmado > 0 else None


# ---------------------------------------------------------------------------
# UF da meta física — count(distinct)=1 + "primeira ocorrência" é o jeito
# de "pegar o valor quando é único": com mais de uma UF distinta, o valor
# não seria usado mesmo (vira "Múltiplas UFs"), então a escolha entre
# primeira ocorrência ou qualquer outra não importa nesse caso.
# ---------------------------------------------------------------------------
def montar_uf_metas(meta_crono_fisico: list[dict]) -> dict[str, dict]:
    """{nr_convenio: {"n_ufs_meta": int, "uf_meta_unica": str}}."""
    ufs_por_convenio: dict[str, set[str]] = defaultdict(set)
    primeira_uf: dict[str, str] = {}
    for m in meta_crono_fisico:
        nr = _txt(m.get("nr_convenio"))
        uf = _limpa_uf(m.get("uf_meta"))
        if not nr or not uf:
            continue
        if nr not in primeira_uf:
            primeira_uf[nr] = uf
        ufs_por_convenio[nr].add(uf)
    return {
        nr: {"n_ufs_meta": len(ufs), "uf_meta_unica": primeira_uf[nr]}
        for nr, ufs in ufs_por_convenio.items()
    }


# ---------------------------------------------------------------------------
# Universo e grão 1 instrumento (mesmo universo do I1 Convênios)
# ---------------------------------------------------------------------------
def montar_instrumentos(
    gold_convenios: list[dict], meta_crono_fisico: list[dict],
    ano_corte: int = ANO_CORTE,
    excluir_empenho_zero_com_pago: bool = EXCLUIR_EMPENHO_ZERO_COM_PAGO,
) -> list[dict]:
    uf_metas = montar_uf_metas(meta_crono_fisico)

    instrumentos = []
    for r in gold_convenios:
        ano = _ano_instrumento(r.get("data_assinatura"), r.get("inicio_vigencia"))
        if ano is None or ano < ano_corte:
            continue
        situacao_norm = _sem_acento(_txt(r.get("situacao_atual")).lower())
        if situacao_norm in SITUACOES_EXCLUIDAS:
            continue

        firmado_atualizado = _num(r.get("valor_firmado_atualizado"))
        firmado = round(
            firmado_atualizado if firmado_atualizado > 0
            else _num(r.get("valor_firmado_inicial")),
            2,
        )
        empenhado = round(_num(r.get("valor_empenhado")), 2)
        pago = round(_num(r.get("valor_total_pago")), 2)
        qualidade = _qualidade_dado(empenhado, pago, firmado)
        if excluir_empenho_zero_com_pago and qualidade == "empenho_zero_com_pagamento":
            continue

        nr = _txt(r.get("nr_convenio"))
        uf_sede = _limpa_uf(r.get("uf_execucao"))
        meta_info = uf_metas.get(nr)
        if meta_info and meta_info["n_ufs_meta"] > 1:
            uf, fonte_uf = ROTULO_MULTIPLAS, "meta"
        elif meta_info and meta_info["n_ufs_meta"] == 1:
            uf, fonte_uf = meta_info["uf_meta_unica"], "meta"
        elif uf_sede:
            uf, fonte_uf = uf_sede, "sede"
        else:
            uf, fonte_uf = ROTULO_SEM_UF, "sem_informacao"

        instrumentos.append({
            "nr_convenio": nr,
            "modalidade": _txt(r.get("modalidade_instrumento")).title(),
            "ano": ano,
            "origem": ROTULO_EMENDA if _txt(r.get("parlamentares")) else ROTULO_REGULAR,
            "firmado": firmado,
            "empenhado": empenhado,
            "pago": pago,
            "qualidade_dado": qualidade,
            "uf": uf,
            "fonte_uf": fonte_uf,
        })
    return instrumentos


# ---------------------------------------------------------------------------
# Ranking de UFs por firmado total -> uf_grupo / ordem_uf
# ---------------------------------------------------------------------------
def montar_ranking_uf(
    instrumentos: list[dict], n_ufs_destaque: int = N_UFS_DESTAQUE
) -> dict[str, dict]:
    firmado_por_uf: dict[str, float] = defaultdict(float)
    for i in instrumentos:
        firmado_por_uf[i["uf"]] += i["firmado"]

    ordenadas = sorted(firmado_por_uf.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        uf: (
            {"uf_grupo": uf, "ordem_uf": posicao}
            if posicao <= n_ufs_destaque
            else {"uf_grupo": ROTULO_DEMAIS, "ordem_uf": n_ufs_destaque + 1}
        )
        for posicao, (uf, _) in enumerate(ordenadas, start=1)
    }


# ---------------------------------------------------------------------------
# Agregações
# ---------------------------------------------------------------------------
def montar_fato(instrumentos: list[dict]) -> list[dict]:
    acc: dict[tuple, dict] = defaultdict(lambda: {
        "n_instrumentos": 0, "firmado": 0.0, "empenhado": 0.0, "pago": 0.0,
    })
    for i in instrumentos:
        chave = (
            i["uf"], i["uf_grupo"], i["ordem_uf"], i["fonte_uf"], i["ano"],
            i["origem"], i["modalidade"], i["qualidade_dado"],
        )
        a = acc[chave]
        a["n_instrumentos"] += 1
        a["firmado"] += i["firmado"]
        a["empenhado"] += i["empenhado"]
        a["pago"] += i["pago"]

    linhas = [
        {
            "uf": c[0], "uf_grupo": c[1], "ordem_uf": c[2], "fonte_uf": c[3], "ano": c[4],
            "origem": c[5], "modalidade": c[6], "qualidade_dado": c[7],
            "n_instrumentos": v["n_instrumentos"], "firmado": round(v["firmado"], 2),
            "empenhado": round(v["empenhado"], 2), "pago": round(v["pago"], 2),
        }
        for c, v in acc.items()
    ]
    linhas.sort(key=lambda l: (l["ordem_uf"], l["uf"], l["ano"], l["origem"], l["modalidade"], l["qualidade_dado"]))
    return linhas


def montar_heatmap(instrumentos: list[dict]) -> list[dict]:
    """Grade completa uf_grupo x ano — célula sem convênio fica com n=0 e taxa vazia."""
    grupos = sorted({(i["uf_grupo"], i["ordem_uf"]) for i in instrumentos}, key=lambda g: g[1])
    anos = sorted({i["ano"] for i in instrumentos})

    acc: dict[tuple, dict] = defaultdict(lambda: {"n_instrumentos": 0, "firmado": 0.0, "pago": 0.0})
    for i in instrumentos:
        a = acc[(i["uf_grupo"], i["ordem_uf"], i["ano"])]
        a["n_instrumentos"] += 1
        a["firmado"] += i["firmado"]
        a["pago"] += i["pago"]

    linhas = []
    for uf_grupo, ordem_uf in grupos:
        for ano in anos:
            v = acc.get((uf_grupo, ordem_uf, ano), {"n_instrumentos": 0, "firmado": 0.0, "pago": 0.0})
            firmado = round(v["firmado"], 2)
            pago = round(v["pago"], 2)
            linhas.append({
                "uf_grupo": uf_grupo,
                "ordem_uf": ordem_uf,
                "ano": ano,
                "n_instrumentos": v["n_instrumentos"],
                "firmado": firmado,
                "pago": pago,
                "taxa_execucao_pct": _taxa(pago, firmado) if v["n_instrumentos"] > 0 else None,
            })
    linhas.sort(key=lambda l: (l["ordem_uf"], l["ano"]))
    return linhas


def montar_cartoes_ano(instrumentos: list[dict]) -> list[dict]:
    acc: dict[int | None, dict] = defaultdict(lambda: {"n_instrumentos": 0, "firmado": 0.0, "pago": 0.0})
    for i in instrumentos:
        a = acc[i["ano"]]
        a["n_instrumentos"] += 1
        a["firmado"] += i["firmado"]
        a["pago"] += i["pago"]

    linhas = [
        {
            "ano": ano,
            "n_instrumentos": v["n_instrumentos"],
            "firmado": round(v["firmado"], 2),
            "pago": round(v["pago"], 2),
            "taxa_execucao_pct": _taxa(round(v["pago"], 2), round(v["firmado"], 2)),
        }
        for ano, v in acc.items()
    ]
    linhas.sort(key=lambda l: l["ano"])
    return linhas


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def calcular_i1b(gold_convenios: list[dict], meta_crono_fisico: list[dict]) -> dict[str, list[dict]]:
    """Calcula as três saídas do I1b."""
    instrumentos = montar_instrumentos(gold_convenios, meta_crono_fisico)
    if not instrumentos:
        raise ValueError("Universo vazio: confira ANO_CORTE e as situações excluídas.")

    ranking = montar_ranking_uf(instrumentos)
    for i in instrumentos:
        i.update(ranking[i["uf"]])

    fato = montar_fato(instrumentos)
    heatmap = montar_heatmap(instrumentos)
    cartoes_ano = montar_cartoes_ano(instrumentos)

    firm_total = sum(i["firmado"] for i in instrumentos)
    pago_total = sum(i["pago"] for i in instrumentos)

    def _bate(a: float, b: float) -> bool:
        return abs(a - b) < 0.05

    assert _bate(sum(f["firmado"] for f in fato), firm_total)
    assert _bate(sum(f["pago"] for f in fato), pago_total)
    assert _bate(sum(h["firmado"] for h in heatmap), firm_total)
    assert _bate(sum(h["pago"] for h in heatmap), pago_total)
    assert sum(h["n_instrumentos"] for h in heatmap) == len(instrumentos)
    assert sum(c["n_instrumentos"] for c in cartoes_ano) == len(instrumentos)

    return {
        "i1b_convenio_uf_ano_fato": fato,
        "i1b_convenio_heatmap": heatmap,
        "i1b_convenio_cartoes_ano": cartoes_ano,
    }
