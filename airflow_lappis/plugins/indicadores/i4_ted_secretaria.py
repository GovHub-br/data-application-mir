"""Indicador I4 (TED) — Valor por Secretaria do MIR.

Porte de ``I4/i4_ted_bi.R`` (equipe de BI, pacote Bloco 1). Indicador NOVO —
não existe para Convênios/Fomentos (o gold de convênio não traz secretaria).

Substitui o I4 da entrega anterior (``i4_ted_secretaria_x_programa.R``, zip
``MIR_Scripts_R_TED.zip``), que cruzava secretaria x programa PPA. Esta
versão do Bloco 1 tira o programa PPA do I4 (vira indicador futuro, ainda
não entregue) e muda o valor de empenhado líquido para firmado.

DEFINIÇÕES:
 - Secretaria = ``sigla_unidade_responsavel_acompanhamento`` de
   ``programas_ted``, ligada ao plano via ``id_programa``. Esse vínculo
   existe desde a criação do plano — por isso cobre todos os TEDs, diferente
   do programa PPA (que só aparece depois da Nota de Crédito).
 - "Sem secretaria" = TEDs geridos diretamente pelo ministério, sem
   secretaria delegada identificada.
 - Valor = firmado (``vl_total_plano_acao``). Não é taxa de execução.
 - Universo: mesmo do I1 novo (planos exceto REJEITADO, dedup por
   id_plano_acao mantendo a primeira ocorrência).
 - Origem: mesma lógica 3 vias do I1 novo (Emenda/Regular/Sem informação,
   via ``ted_resumo_orcamentario``).

Fontes (tabelas dbt — já usadas por outros indicadores, sem mudança de schema):
    siafi_dbt.planos_acao_ted         → cadastro, firmado, ano, situação
    siafi_dbt.programas_ted           → secretaria (via id_programa)
    siafi_dbt.ted_resumo_orcamentario → usado só para a coluna origem

Saídas (4):
    i4_ted_secretaria_fato     — grão 1 TED: secretaria, ano, origem, firmado
    i4_ted_secretaria_barras   — barras sem ano (tela principal)
    i4_ted_secretaria_por_ano  — barras por ano de assinatura (tela secundária)
    i4_ted_secretaria_cartao   — 1 linha, resumo da tela
"""

from collections import defaultdict
from typing import Any

SITUACOES_EXCLUIDAS_TED = {"REJEITADO"}
ROTULO_REGULAR = "Regular"
ROTULO_EMENDA = "Emenda"
ROTULO_SEM_INFO = "Sem informação"
ROTULO_SEM_SECRETARIA = "Sem secretaria"


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


# ---------------------------------------------------------------------------
# Origem — mesma lógica do I1/I3 novos (duplicada de propósito).
# ---------------------------------------------------------------------------
def calcular_origem_por_plano(resumo: list[dict]) -> dict[str, str]:
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


# ---------------------------------------------------------------------------
# Secretaria por programa — vínculo existe desde a criação do plano.
# ---------------------------------------------------------------------------
def montar_secretaria_e_nomes(prog: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """Retorna ({id_programa: secretaria}, {secretaria: primeiro nome não vazio})."""
    vistos: set[str] = set()
    secretaria_por_programa: dict[str, str] = {}
    nomes: dict[str, str] = {}
    for r in prog:
        pid = _txt(r.get("id_programa"))
        if not pid or pid in vistos:
            continue
        vistos.add(pid)
        secretaria = _txt(r.get("sigla_unidade_responsavel_acompanhamento"))
        nome = _txt(r.get("unidade_responsavel_acompanhamento"))
        secretaria_por_programa[pid] = secretaria
        if secretaria and nome and secretaria not in nomes:
            nomes[secretaria] = nome
    return secretaria_por_programa, nomes


# ---------------------------------------------------------------------------
# Universo e grão 1 TED
# ---------------------------------------------------------------------------
def montar_fato(planos: list[dict], prog: list[dict], resumo: list[dict]) -> list[dict]:
    secretaria_por_programa, _ = montar_secretaria_e_nomes(prog)
    origem_por_plano = calcular_origem_por_plano(resumo)

    # Dedup por id_plano_acao, mantendo a primeira ocorrência.
    vistos: set[str] = set()
    fato = []
    for p in planos:
        pid = _txt(p.get("id_plano_acao"))
        if not pid or pid in vistos:
            continue
        vistos.add(pid)

        situacao = _txt(p.get("tx_situacao_plano_acao"))
        if situacao.upper() in SITUACOES_EXCLUIDAS_TED:
            continue

        id_programa = _txt(p.get("id_programa"))
        secretaria = secretaria_por_programa.get(id_programa, "") or ROTULO_SEM_SECRETARIA
        fato.append({
            "id_plano_acao": pid,
            "secretaria": secretaria,
            "ano": _ano_int(p.get("aa_ano_plano_acao")),
            "origem": origem_por_plano.get(pid, ROTULO_SEM_INFO),
            "firmado": round(_num(p.get("vl_total_plano_acao")), 2),
        })
    return fato


# ---------------------------------------------------------------------------
# Agregações
# ---------------------------------------------------------------------------
def montar_barras(fato: list[dict], nomes: dict[str, str]) -> list[dict]:
    firm_total = sum(f["firmado"] for f in fato)
    acc: dict[str, dict] = defaultdict(lambda: {"n_teds": 0, "firmado": 0.0})
    for f in fato:
        a = acc[f["secretaria"]]
        a["n_teds"] += 1
        a["firmado"] += f["firmado"]

    linhas = sorted(
        (
            {
                "secretaria": secretaria,
                "nome_secretaria": nomes.get(secretaria, ""),
                "n_teds": v["n_teds"],
                "firmado": round(v["firmado"], 2),
                "pct_do_total": round(100 * v["firmado"] / firm_total, 1) if firm_total else 0.0,
            }
            for secretaria, v in acc.items()
        ),
        key=lambda l: (-l["firmado"], l["secretaria"]),
    )
    return [{"ordem_exibicao": i, **l} for i, l in enumerate(linhas, start=1)]


def montar_por_ano(fato: list[dict], nomes: dict[str, str]) -> list[dict]:
    acc: dict[tuple, dict] = defaultdict(lambda: {"n_teds": 0, "firmado": 0.0})
    total_por_ano: dict[int | None, float] = defaultdict(float)
    for f in fato:
        chave = (f["ano"], f["secretaria"])
        a = acc[chave]
        a["n_teds"] += 1
        a["firmado"] += f["firmado"]
        total_por_ano[f["ano"]] += f["firmado"]

    linhas = [
        {
            "ano": ano,
            "secretaria": secretaria,
            "nome_secretaria": nomes.get(secretaria, ""),
            "n_teds": v["n_teds"],
            "firmado": round(v["firmado"], 2),
            "pct_do_total_ano": (
                round(100 * v["firmado"] / total_por_ano[ano], 1) if total_por_ano[ano] else 0.0
            ),
        }
        for (ano, secretaria), v in acc.items()
    ]
    linhas.sort(key=lambda l: (l["ano"] is None, l["ano"], -l["firmado"], l["secretaria"]))
    return linhas


def montar_cartao(fato: list[dict], barras: list[dict]) -> list[dict]:
    firm_total = sum(f["firmado"] for f in fato)
    n_teds = len(fato)
    n_sem = sum(1 for f in fato if f["secretaria"] == ROTULO_SEM_SECRETARIA)
    top = barras[0]
    return [{
        "firmado_total": round(firm_total, 2),
        "n_teds": n_teds,
        "maior_secretaria": top["secretaria"],
        "firmado_maior_secretaria": top["firmado"],
        "n_secretarias": sum(1 for b in barras if b["secretaria"] != ROTULO_SEM_SECRETARIA),
        "pct_campo_preenchido": round(100 * (n_teds - n_sem) / n_teds, 1) if n_teds else 0.0,
    }]


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def calcular_i4(planos: list[dict], prog: list[dict], resumo: list[dict]) -> dict[str, list[dict]]:
    """Calcula as quatro saídas do I4 (TED)."""
    _, nomes = montar_secretaria_e_nomes(prog)
    fato = montar_fato(planos, prog, resumo)
    if not fato:
        raise ValueError("Universo vazio: confira as situações excluídas.")

    barras = montar_barras(fato, nomes)
    por_ano = montar_por_ano(fato, nomes)
    cartao = montar_cartao(fato, barras)

    def _bate(a: float, b: float) -> bool:
        return abs(a - b) < 0.05

    firm_total = sum(f["firmado"] for f in fato)
    assert _bate(sum(b["firmado"] for b in barras), firm_total)
    assert _bate(sum(l["firmado"] for l in por_ano), firm_total)
    assert sum(b["n_teds"] for b in barras) == len(fato)
    assert sum(l["n_teds"] for l in por_ano) == len(fato)

    return {
        "i4_ted_secretaria_fato": fato,
        "i4_ted_secretaria_barras": barras,
        "i4_ted_secretaria_por_ano": por_ano,
        "i4_ted_secretaria_cartao": cartao,
    }
