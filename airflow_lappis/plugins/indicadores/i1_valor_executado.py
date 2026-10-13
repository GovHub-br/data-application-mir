"""Indicador I1 — Valor Executado por Instrumento.

Porte de ``I1/i1_ted_bi.R`` e ``I1/i1_convenios_bi.R`` (equipe de BI, pacote
Bloco 1) para funções puras. Substitui a versão anterior deste indicador
(baseada em ``i1_etapa_cadeia_ted.R``, 2026-07-21) — metodologia nova,
confirmada no documento "alteracoes_scripts_engenharia_dados_atualizado.docx"
que acompanha o pacote.

TED e Convênios/Fomentos são calculados por módulos independentes
(``calcular_i1_ted`` / ``calcular_i1_convenios``) e combinados em
``calcular_i1``.

PRINCIPAIS MUDANÇAS EM RELAÇÃO À VERSÃO ANTERIOR:

TED:
 1. Fonte da execução financeira TROCOU: antes somava ``ted_resumo_orcamentario``
    por plano; agora soma ``ted_empenhos_plano_acao`` (notas de empenho) por
    plano. ``ted_resumo_orcamentario`` passa a ser usado só para a origem do
    recurso. Motivo: o resumo orçamentário inclui transferências fora do
    universo MIR e infla os totais.
 2. ``empenhado`` não subtrai mais um campo de anulação à parte:
    ``despesas_empenhadas`` já vem com o sinal da anulação embutido.
 3. ``liquidado`` é campo novo (não existia na versão anterior).
 4. ``pago`` MUDA DE DEFINIÇÃO: antes era despesas pagas no exercício + RAP
    pagos; agora é SÓ despesas pagas. RAP fica em colunas à parte
    (``rap_inscritos``/``rap_pagos``), só para consulta — decisão da
    coordenação, não incluir RAP nos totais/cartões.
 5. ``origem`` não depende mais de ``instrumentos_emendas``— vem direto da
    coluna ``origem`` do ``ted_resumo_orcamentario`` (três categorias:
    Emenda / Regular / Sem informação).
 6. ``etapa_cadeia`` (funil PF→NC→NE) REMOVIDO. Sem substituto no pacote
    atual.
 7. ``classe_programa_ppa`` e ``secretaria_gestora`` REMOVIDOS — a secretaria
    passa a vir do I4 (join por id_plano_acao, se precisar).
 8. Dois eixos de tempo, não um: "ano de assinatura" (``aa_ano_plano_acao``)
    e "ano de execução" (``ne_ccor_ano_emissao``, da nota de empenho).
 9. Universo: igual (todos os planos exceto REJEITADO), mas com dedup por
    id_plano_acao (mantém a primeira ocorrência).

Convênios/Fomentos:
 1. Território (UF/município) SAI do I1 — vira o indicador I1b (separado,
    fora do escopo deste módulo), que usa a UF da meta física em vez da UF
    "de execução" da gold (que, na prática, é a sede do convenente).
 2. NOVO: coluna ``qualidade_dado`` por instrumento (``empenho_zero_com_pagamento``,
    ``pago_maior_que_empenhado``, ``sem_empenho``, ``empenho_parcial``, ``ok``;
    primeira condição que bate vence). ``empenho_zero_com_pagamento`` é
    excluído do universo por padrão e listado à parte.
 3. ``firmado``: usa ``valor_firmado_atualizado``; se vier <= 0, cai para
    ``valor_firmado_inicial``.
 4. Universo (igual): ano de assinatura (fallback início de vigência) >= 2023;
    exclui situação Cancelado/Convênio Anulado — e agora também exclui
    ``empenho_zero_com_pagamento`` por padrão.

Fontes (tabelas dbt):
    siafi_dbt.planos_acao_ted         → cadastro dos TEDs
    siafi_dbt.ted_empenhos_plano_acao → notas de empenho (fonte da execução)
    siafi_dbt.ted_resumo_orcamentario → usado só para a coluna origem do TED
    siconv_dbt.resumo_convenios       → convênios/fomentos consolidados

Saídas (13):
    i1_ted_cartoes, i1_ted_safra_origem, i1_ted_execucao_ano, i1_ted_por_ano,
    i1_ted_por_origem, i1_ted_instrumentos,
    i1_convenio_cartoes, i1_convenio_fato_ano, i1_convenio_por_ano,
    i1_convenio_por_origem, i1_convenio_instrumentos, i1_convenio_qualidade,
    i1_convenio_excluidos
"""

import unicodedata
from collections import defaultdict
from datetime import date, datetime
from typing import Any

ANO_CORTE_CONVENIO = 2023
SITUACOES_EXCLUIDAS_TED = {"REJEITADO"}
SITUACOES_EXCLUIDAS_CONVENIO = {"cancelado", "convenio anulado"}
EXCLUIR_EMPENHO_ZERO_COM_PAGO = True
ROTULO_REGULAR = "Regular"
ROTULO_EMENDA = "Emenda"
ROTULO_SEM_INFO = "Sem informação"


# ---------------------------------------------------------------------------
# Normalização: os valores podem vir tipados do Postgres ou em texto (CSV)
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


def _ano_int(valor: Any) -> int | None:
    texto = _txt(valor)
    try:
        return int(float(texto)) if texto else None
    except ValueError:
        return None


def _pct(parte: float, total: float) -> float | None:
    return round(100 * parte / total, 1) if total else None


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


def _ano_instrumento_convenio(data_assinatura: Any, inicio_vigencia: Any) -> int | None:
    return _ano_data(data_assinatura) or _ano_data(inicio_vigencia)


# ===========================================================================
# TED
# ===========================================================================
def calcular_origem_por_plano(resumo: list[dict]) -> dict[str, str]:
    """Origem do recurso: vem do ted_resumo_orcamentario, não mais de instrumentos_emendas."""
    por_plano: dict[str, set[str]] = defaultdict(set)
    for r in resumo:
        pid = _txt(r.get("plano_acao"))
        if not pid:
            continue
        por_plano[pid].add(_txt(r.get("origem")).lower())

    origem: dict[str, str] = {}
    for pid, valores in por_plano.items():
        if any(v.startswith("emenda") for v in valores):
            origem[pid] = ROTULO_EMENDA
        elif any(v.startswith("recurso") for v in valores):
            origem[pid] = ROTULO_REGULAR
        else:
            origem[pid] = ROTULO_SEM_INFO
    return origem


def calcular_execucao_por_plano(empenhos: list[dict]) -> dict[str, dict]:
    """Execução financeira: soma ted_empenhos_plano_acao por plano."""
    acc: dict[str, dict] = defaultdict(lambda: {
        "empenhado": 0.0, "liquidado": 0.0, "pago": 0.0,
        "rap_inscritos": 0.0, "rap_pagos": 0.0, "n_notas_empenho": 0,
    })
    for e in empenhos:
        pid = _txt(e.get("plano_acao"))
        if not pid:
            continue
        a = acc[pid]
        a["empenhado"] += _num(e.get("despesas_empenhadas"))
        a["liquidado"] += _num(e.get("despesas_liquidadas"))
        a["pago"] += _num(e.get("despesas_pagas"))
        a["rap_inscritos"] += _num(e.get("restos_a_pagar_inscritos"))
        a["rap_pagos"] += _num(e.get("restos_a_pagar_pagos"))
        a["n_notas_empenho"] += 1
    return dict(acc)


def calcular_execucao_por_plano_ano(empenhos: list[dict]) -> list[dict]:
    """Execução por (plano, ano de emissão da nota) — eixo "ano de execução"."""
    acc: dict[tuple, dict] = defaultdict(lambda: {
        "empenhado": 0.0, "liquidado": 0.0, "pago": 0.0,
    })
    for e in empenhos:
        pid = _txt(e.get("plano_acao"))
        if not pid:
            continue
        ano_exec = _ano_int(e.get("ne_ccor_ano_emissao"))
        chave = (pid, ano_exec)
        a = acc[chave]
        a["empenhado"] += _num(e.get("despesas_empenhadas"))
        a["liquidado"] += _num(e.get("despesas_liquidadas"))
        a["pago"] += _num(e.get("despesas_pagas"))
    return [
        {"plano_acao": pid, "ano_execucao": ano_exec, **v}
        for (pid, ano_exec), v in acc.items()
    ]


def montar_instrumentos_ted(
    planos: list[dict], empenhos: list[dict], resumo: list[dict]
) -> list[dict]:
    # Dedup por id_plano_acao, mantendo a primeira ocorrência.
    vistos: set[str] = set()
    planos_dedup = []
    for p in planos:
        pid = _txt(p.get("id_plano_acao"))
        if pid and pid not in vistos:
            vistos.add(pid)
            planos_dedup.append(p)

    exec_por_plano = calcular_execucao_por_plano(empenhos)
    origem_por_plano = calcular_origem_por_plano(resumo)

    instrumentos = []
    for p in planos_dedup:
        situacao = _txt(p.get("tx_situacao_plano_acao"))
        if situacao.upper() in SITUACOES_EXCLUIDAS_TED:
            continue

        pid = _txt(p.get("id_plano_acao"))
        exe = exec_por_plano.get(pid, {})
        empenhado = round(exe.get("empenhado", 0.0), 2)
        instrumentos.append({
            "id_plano_acao": pid,
            "ano": _ano_int(p.get("aa_ano_plano_acao")),
            "situacao": situacao,
            "origem": origem_por_plano.get(pid, ROTULO_SEM_INFO),
            "firmado": round(_num(p.get("vl_total_plano_acao")), 2),
            "empenhado": empenhado,
            "liquidado": round(exe.get("liquidado", 0.0), 2),
            "pago": round(exe.get("pago", 0.0), 2),
            "rap_inscritos": round(exe.get("rap_inscritos", 0.0), 2),
            "rap_pagos": round(exe.get("rap_pagos", 0.0), 2),
            "sem_empenho": 1 if empenhado == 0 else 0,
        })
    return instrumentos


def calcular_cartoes_ted(instrumentos: list[dict]) -> list[dict]:
    firmado = round(sum(i["firmado"] for i in instrumentos), 2)
    empenhado = round(sum(i["empenhado"] for i in instrumentos), 2)
    liquidado = round(sum(i["liquidado"] for i in instrumentos), 2)
    pago = round(sum(i["pago"] for i in instrumentos), 2)
    n_teds = len(instrumentos)
    return [
        {"ordem": 1, "etapa": "Firmado", "valor": firmado, "n_teds": n_teds},
        {"ordem": 2, "etapa": "Empenhado", "valor": empenhado, "n_teds": n_teds},
        {"ordem": 3, "etapa": "Liquidado", "valor": liquidado, "n_teds": n_teds},
        {"ordem": 4, "etapa": "Pago", "valor": pago, "n_teds": n_teds},
    ]


def _resumir_ted(instrumentos: list[dict], chave) -> list[dict]:
    acc: dict = defaultdict(lambda: {
        "n_teds": 0, "firmado": 0.0, "empenhado": 0.0, "liquidado": 0.0,
        "pago": 0.0, "n_sem_empenho": 0,
    })
    for i in instrumentos:
        a = acc[chave(i)]
        a["n_teds"] += 1
        a["firmado"] += i["firmado"]
        a["empenhado"] += i["empenhado"]
        a["liquidado"] += i["liquidado"]
        a["pago"] += i["pago"]
        a["n_sem_empenho"] += i["sem_empenho"]
    return [
        {**({"chave": k} if not isinstance(k, tuple) else dict(zip(("ano", "origem"), k))),
         "n_teds": v["n_teds"],
         "firmado": round(v["firmado"], 2),
         "empenhado": round(v["empenhado"], 2),
         "liquidado": round(v["liquidado"], 2),
         "pago": round(v["pago"], 2),
         "n_sem_empenho": v["n_sem_empenho"]}
        for k, v in acc.items()
    ]


def agregar_ted_por_ano(instrumentos: list[dict]) -> list[dict]:
    linhas = _resumir_ted(instrumentos, lambda i: i["ano"])
    for l in linhas:
        l["ano"] = l.pop("chave")
    linhas.sort(key=lambda l: (l["ano"] is None, l["ano"]))
    firm_total = sum(l["firmado"] for l in linhas)
    for l in linhas:
        l["pct_do_firmado_total"] = _pct(l["firmado"], firm_total)
    return linhas


def agregar_ted_por_origem(instrumentos: list[dict]) -> list[dict]:
    linhas = _resumir_ted(instrumentos, lambda i: i["origem"])
    for l in linhas:
        l["origem"] = l.pop("chave")
    ordem = {ROTULO_REGULAR: 0, ROTULO_SEM_INFO: 1, ROTULO_EMENDA: 2}
    linhas.sort(key=lambda l: ordem.get(l["origem"], 99))
    firm_total = sum(l["firmado"] for l in linhas)
    for l in linhas:
        l["pct_do_firmado_total"] = _pct(l["firmado"], firm_total)
    return linhas


def agregar_safra_origem(instrumentos: list[dict]) -> list[dict]:
    linhas = _resumir_ted(instrumentos, lambda i: (i["ano"], i["origem"]))
    linhas.sort(key=lambda l: (l["ano"] is None, l["ano"], l["origem"]))
    return linhas


def agregar_execucao_ano(
    instrumentos: list[dict], execucao_por_plano_ano: list[dict]
) -> list[dict]:
    origem_por_plano = {i["id_plano_acao"]: i["origem"] for i in instrumentos}
    universo = set(origem_por_plano)

    acc: dict[tuple, dict] = defaultdict(lambda: {
        "planos": set(), "empenhado": 0.0, "liquidado": 0.0, "pago": 0.0,
    })
    for e in execucao_por_plano_ano:
        pid = e["plano_acao"]
        if pid not in universo:
            continue
        chave = (e["ano_execucao"], origem_por_plano[pid])
        a = acc[chave]
        a["planos"].add(pid)
        a["empenhado"] += e["empenhado"]
        a["liquidado"] += e["liquidado"]
        a["pago"] += e["pago"]

    linhas = [
        {
            "ano_execucao": ano_exec,
            "origem": origem,
            "n_teds": len(v["planos"]),
            "empenhado": round(v["empenhado"], 2),
            "liquidado": round(v["liquidado"], 2),
            "pago": round(v["pago"], 2),
        }
        for (ano_exec, origem), v in acc.items()
    ]
    linhas.sort(key=lambda l: (l["ano_execucao"] is None, l["ano_execucao"], l["origem"]))
    return linhas


def calcular_i1_ted(
    planos: list[dict], empenhos: list[dict], resumo: list[dict]
) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I1 (TED)."""
    instrumentos = montar_instrumentos_ted(planos, empenhos, resumo)
    if not instrumentos:
        raise ValueError("Universo vazio: confira as situações excluídas.")

    cartoes = calcular_cartoes_ted(instrumentos)
    tot = {c["etapa"].lower(): c["valor"] for c in cartoes}

    por_ano = agregar_ted_por_ano(instrumentos)
    por_origem = agregar_ted_por_origem(instrumentos)
    safra_origem = agregar_safra_origem(instrumentos)

    exec_por_plano_ano = calcular_execucao_por_plano_ano(empenhos)
    execucao_ano = agregar_execucao_ano(instrumentos, exec_por_plano_ano)

    def _bate(a: float, b: float) -> bool:
        return abs(a - b) < 0.05

    assert _bate(sum(l["firmado"] for l in safra_origem), tot["firmado"])
    assert _bate(sum(l["pago"] for l in safra_origem), tot["pago"])
    assert _bate(sum(l["firmado"] for l in por_ano), tot["firmado"])
    assert _bate(sum(l["firmado"] for l in por_origem), tot["firmado"])
    assert _bate(sum(l["pago"] for l in por_ano), tot["pago"])
    assert _bate(sum(l["empenhado"] for l in por_origem), tot["empenhado"])
    if execucao_ano:
        assert _bate(sum(l["empenhado"] for l in execucao_ano), tot["empenhado"])
        assert _bate(sum(l["liquidado"] for l in execucao_ano), tot["liquidado"])
        assert _bate(sum(l["pago"] for l in execucao_ano), tot["pago"])

    return {
        "i1_ted_cartoes": cartoes,
        "i1_ted_safra_origem": safra_origem,
        "i1_ted_execucao_ano": execucao_ano,
        "i1_ted_por_ano": por_ano,
        "i1_ted_por_origem": por_origem,
        "i1_ted_instrumentos": instrumentos,
    }


# ===========================================================================
# Convênios/Fomentos
# ===========================================================================
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


def montar_instrumentos_convenio(
    gold: list[dict], ano_corte: int = ANO_CORTE_CONVENIO,
    excluir_empenho_zero_com_pago: bool = EXCLUIR_EMPENHO_ZERO_COM_PAGO,
) -> tuple[list[dict], list[dict]]:
    """Retorna (instrumentos_no_universo, excluidos_por_empenho_zero_com_pagamento)."""
    todos = []
    for r in gold:
        ano = _ano_instrumento_convenio(r.get("data_assinatura"), r.get("inicio_vigencia"))
        if ano is None or ano < ano_corte:
            continue
        situacao_norm = _sem_acento(_txt(r.get("situacao_atual")).lower())
        if situacao_norm in SITUACOES_EXCLUIDAS_CONVENIO:
            continue

        firmado_atualizado = _num(r.get("valor_firmado_atualizado"))
        firmado = round(
            firmado_atualizado if firmado_atualizado > 0
            else _num(r.get("valor_firmado_inicial")),
            2,
        )
        empenhado = round(_num(r.get("valor_empenhado")), 2)
        pago = round(_num(r.get("valor_total_pago")), 2)

        todos.append({
            "nr_convenio": _txt(r.get("nr_convenio")),
            "modalidade": _txt(r.get("modalidade_instrumento")).title(),
            "ano": ano,
            "origem": ROTULO_EMENDA if _txt(r.get("parlamentares")) else ROTULO_REGULAR,
            "situacao": _txt(r.get("situacao_atual")),
            "firmado": firmado,
            "empenhado": empenhado,
            "pago": pago,
            "sem_empenho": 1 if empenhado == 0 else 0,
            "qualidade_dado": _qualidade_dado(empenhado, pago, firmado),
        })

    excluidos = [i for i in todos if i["qualidade_dado"] == "empenho_zero_com_pagamento"]
    if excluir_empenho_zero_com_pago:
        instrumentos = [i for i in todos if i["qualidade_dado"] != "empenho_zero_com_pagamento"]
    else:
        instrumentos = todos
    return instrumentos, excluidos


def calcular_cartoes_convenio(instrumentos: list[dict]) -> list[dict]:
    firmado = round(sum(i["firmado"] for i in instrumentos), 2)
    empenhado = round(sum(i["empenhado"] for i in instrumentos), 2)
    pago = round(sum(i["pago"] for i in instrumentos), 2)
    n = len(instrumentos)
    return [
        {"ordem": 1, "etapa": "Firmado", "valor": firmado, "n_instrumentos": n},
        {"ordem": 2, "etapa": "Empenhado", "valor": empenhado, "n_instrumentos": n},
        {"ordem": 3, "etapa": "Pago", "valor": pago, "n_instrumentos": n},
    ]


def _resumir_convenio(instrumentos: list[dict], chave) -> dict[Any, dict]:
    acc: dict = defaultdict(lambda: {
        "n_instrumentos": 0, "firmado": 0.0, "empenhado": 0.0, "pago": 0.0, "n_sem_empenho": 0,
    })
    for i in instrumentos:
        a = acc[chave(i)]
        a["n_instrumentos"] += 1
        a["firmado"] += i["firmado"]
        a["empenhado"] += i["empenhado"]
        a["pago"] += i["pago"]
        a["n_sem_empenho"] += i["sem_empenho"]
    return acc


def agregar_convenio_por_ano(instrumentos: list[dict]) -> list[dict]:
    acc = _resumir_convenio(instrumentos, lambda i: i["ano"])
    linhas = [
        {"ano": ano, "n_instrumentos": v["n_instrumentos"], "firmado": round(v["firmado"], 2),
         "empenhado": round(v["empenhado"], 2), "pago": round(v["pago"], 2),
         "n_sem_empenho": v["n_sem_empenho"]}
        for ano, v in acc.items()
    ]
    linhas.sort(key=lambda l: (l["ano"] is None, l["ano"]))
    return linhas


def agregar_convenio_por_origem(instrumentos: list[dict]) -> list[dict]:
    acc = _resumir_convenio(instrumentos, lambda i: i["origem"])
    linhas = [
        {"origem": origem, "n_instrumentos": v["n_instrumentos"], "firmado": round(v["firmado"], 2),
         "empenhado": round(v["empenhado"], 2), "pago": round(v["pago"], 2),
         "n_sem_empenho": v["n_sem_empenho"]}
        for origem, v in acc.items()
    ]
    ordem = {ROTULO_REGULAR: 0, ROTULO_EMENDA: 1}
    linhas.sort(key=lambda l: ordem.get(l["origem"], 99))
    return linhas


def agregar_fato_ano(instrumentos: list[dict]) -> list[dict]:
    acc = _resumir_convenio(instrumentos, lambda i: (i["ano"], i["origem"], i["modalidade"], i["qualidade_dado"]))
    linhas = [
        {"ano": chave[0], "origem": chave[1], "modalidade": chave[2], "qualidade_dado": chave[3],
         "n_instrumentos": v["n_instrumentos"], "firmado": round(v["firmado"], 2),
         "empenhado": round(v["empenhado"], 2), "pago": round(v["pago"], 2),
         "n_sem_empenho": v["n_sem_empenho"]}
        for chave, v in acc.items()
    ]
    linhas.sort(key=lambda l: (l["ano"] is None, l["ano"], l["origem"], l["modalidade"], l["qualidade_dado"]))
    return linhas


def agregar_qualidade(instrumentos: list[dict]) -> list[dict]:
    acc = _resumir_convenio(instrumentos, lambda i: i["qualidade_dado"])
    total = len(instrumentos)
    return [
        {"qualidade_dado": q, "n_instrumentos": v["n_instrumentos"], "firmado": round(v["firmado"], 2),
         "empenhado": round(v["empenhado"], 2), "pago": round(v["pago"], 2),
         "pct_instrumentos": round(100 * v["n_instrumentos"] / total, 1) if total else 0.0}
        for q, v in acc.items()
    ]


def calcular_i1_convenios(gold: list[dict]) -> dict[str, list[dict]]:
    """Calcula as sete saídas do I1 (Convênios/Fomentos)."""
    instrumentos, excluidos = montar_instrumentos_convenio(gold)
    if not instrumentos:
        raise ValueError("Universo vazio: confira ANO_CORTE_CONVENIO e as situações excluídas.")

    cartoes = calcular_cartoes_convenio(instrumentos)
    por_ano = agregar_convenio_por_ano(instrumentos)
    por_origem = agregar_convenio_por_origem(instrumentos)
    fato_ano = agregar_fato_ano(instrumentos)
    qualidade = agregar_qualidade(instrumentos)

    tot = {c["etapa"].lower(): c["valor"] for c in cartoes}

    def _bate(a: float, b: float) -> bool:
        return abs(a - b) < 0.05

    assert _bate(sum(l["firmado"] for l in fato_ano), sum(i["firmado"] for i in instrumentos))
    assert _bate(sum(l["pago"] for l in fato_ano), sum(i["pago"] for i in instrumentos))
    assert _bate(sum(l["firmado"] for l in por_ano), tot["firmado"])
    assert _bate(sum(l["pago"] for l in por_ano), tot["pago"])
    assert _bate(sum(l["firmado"] for l in por_origem), tot["firmado"])
    assert _bate(sum(l["empenhado"] for l in por_origem), tot["empenhado"])

    return {
        "i1_convenio_cartoes": cartoes,
        "i1_convenio_fato_ano": fato_ano,
        "i1_convenio_por_ano": por_ano,
        "i1_convenio_por_origem": por_origem,
        "i1_convenio_instrumentos": instrumentos,
        "i1_convenio_qualidade": qualidade,
        "i1_convenio_excluidos": excluidos,
    }


# ===========================================================================
# Orquestração
# ===========================================================================
def calcular_i1(
    planos: list[dict],
    empenhos: list[dict],
    resumo: list[dict],
    gold_convenios: list[dict],
) -> dict[str, list[dict]]:
    """Calcula as treze saídas do I1 (TED + Convênios/Fomentos)."""
    return {
        **calcular_i1_ted(planos, empenhos, resumo),
        **calcular_i1_convenios(gold_convenios),
    }
