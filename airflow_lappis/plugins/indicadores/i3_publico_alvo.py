"""Indicador I3 — Público-Alvo por Grupo.

Porte de ``I3/i3_ted_bi.R`` e ``I3/i3_convenios_bi.R`` (equipe de BI, pacote
Bloco 1) para funções puras. Substitui a versão anterior deste indicador
(um único script que processava TED e Convênios juntos). TED e
Convênios/Fomentos agora são dois módulos independentes (``calcular_i3_ted``
/ ``calcular_i3_convenios``), combinados em ``calcular_i3`` — mesmo padrão
do I1.

MÉTODO (sem mudança): busca textual (regex) sobre texto normalizado
(minúsculas, sem acento). TED usa objeto + justificativa do plano de ação;
Convênio usa só o objeto (não há justificativa no gold). Sem camada de
similaridade semântica — limitação conhecida, não implementada.

PRINCIPAIS MUDANÇAS EM RELAÇÃO À VERSÃO ANTERIOR:
 1. Sem subcategorias: ``mulheres_negras``/``estudantes_negros`` saem —
    já contavam em ``pessoas_negras``, sem indicador próprio no pacote
    atual.
 2. Nomenclatura: ``leitura_estrita`` → ``grupo_nomeado``, ``leitura_ampla``
    → ``explicita_publico_racial``, ``racial_generico`` → ``generico``
    (mesmo conceito, nome novo — alinhado ao script R).
 3. TED: origem não depende mais de ``instrumentos_emendas`` — vem direto
    da coluna ``origem`` do ``ted_resumo_orcamentario`` (mesma lógica do
    I1 TED Bloco 1: Emenda/Regular/Sem informação).
 4. Convênios: universo ganha a exclusão de ``empenho_zero_com_pagamento``
    por padrão (mesma regra do I1 Convênios Bloco 1) e os campos
    ``modalidade``/``qualidade_dado`` entram como dimensão do fato.
 5. Saídas mudam de formato: cada módulo devolve fato (instrumento x grupo),
    barras (n e % por grupo, já ordenadas) e cartão (métricas agregadas da
    tela) — em vez de um resumo único e um "grupos" em formato longo.
 6. Categoria "ciganos" mantida (confirmado pela BI: não é marginal nos
    dados reais).

Fontes (tabelas dbt — mesmas do I1, já usadas sem mudança de schema):
    siafi_dbt.planos_acao_ted         → objeto + justificativa do TED
    siafi_dbt.ted_resumo_orcamentario → origem do TED
    siconv_dbt.resumo_convenios       → objeto do convênio/fomento

Saídas (6):
    i3_ted_publico_fato, i3_ted_publico_barras, i3_ted_publico_cartao,
    i3_convenio_publico_fato, i3_convenio_publico_barras,
    i3_convenio_publico_cartao
"""

import re
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
# Normalização
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


def normalizar(texto: str) -> str:
    """Minúsculas + remove acentos, para facilitar o casamento de regex."""
    return _sem_acento((texto or "").lower())


# ---------------------------------------------------------------------------
# Padrões de classificação (aplicados sobre texto em minúsculas, sem acento)
# ---------------------------------------------------------------------------
GRUPOS = {
    "pessoas_negras": "Pessoas negras",
    "quilombolas": "Quilombolas",
    "indigenas": "Indígenas",
    "terreiro": "Povos de terreiro",
    "ciganos": "Ciganos",
}

PADROES = {
    "pessoas_negras": re.compile(
        r"negr[ao]|negras|negros|afro.brasileir|afrodescendent|"
        r"\bpret[ao]\b|pretas|pretos|populacao negra",
        re.IGNORECASE,
    ),
    "quilombolas": re.compile(r"quilombol", re.IGNORECASE),
    "indigenas": re.compile(r"indigen|povos originarios", re.IGNORECASE),
    "terreiro": re.compile(
        r"terreiro|matriz africana|candomble|umbanda|religiosidade afro",
        re.IGNORECASE,
    ),
    # Categoria confirmada nos dados reais, majoritariamente via SQPT.
    "ciganos": re.compile(r"cigan", re.IGNORECASE),
}
# Menção racial genérica (sem nomear um grupo): só entra na leitura ampla.
PADRAO_GENERICO = re.compile(
    r"igualdade racial|antirracist|etnico.racial|relacoes etnico|"
    r"acoes afirmativas|enfrentamento ao racismo|promocao da igualdade",
    re.IGNORECASE,
)


def classificar(*textos: str) -> dict[str, int]:
    """Classifica um instrumento nos grupos de público-alvo."""
    texto = normalizar(" ".join(t or "" for t in textos))
    resultado: dict[str, int] = {
        chave: 1 if padrao.search(texto) else 0 for chave, padrao in PADROES.items()
    }
    resultado["generico"] = 1 if PADRAO_GENERICO.search(texto) else 0
    resultado["grupo_nomeado"] = 1 if any(resultado[g] for g in GRUPOS) else 0
    resultado["explicita_publico_racial"] = (
        1 if (resultado["grupo_nomeado"] or resultado["generico"]) else 0
    )
    return resultado


# ---------------------------------------------------------------------------
# Fato / barras / cartão — compartilhado entre TED e Convênios
# ---------------------------------------------------------------------------
def montar_fato(instrumentos: list[dict], dims: list[str]) -> list[dict]:
    """Formato longo: uma linha por (instrumento, grupo)."""
    fato = []
    for inst in instrumentos:
        base = {"id": inst["id"], **{d: inst[d] for d in dims}}
        for chave, grupo in GRUPOS.items():
            fato.append({
                **base,
                "grupo": grupo,
                "ativo": inst[chave],
                "explicita_publico_racial": inst["explicita_publico_racial"],
            })
    return fato


def montar_barras(fato: list[dict], n_instrumentos: int) -> list[dict]:
    acc: dict[str, int] = defaultdict(int)
    for f in fato:
        acc[f["grupo"]] += f["ativo"]
    ordem_base = {grupo: i for i, grupo in enumerate(GRUPOS.values())}
    linhas = sorted(
        (
            {
                "grupo": grupo,
                "n_instrumentos": n,
                "pct_do_total": round(100 * n / n_instrumentos, 1) if n_instrumentos else 0.0,
            }
            for grupo, n in acc.items()
        ),
        key=lambda l: (-l["n_instrumentos"], ordem_base[l["grupo"]]),
    )
    return [
        {"ordem_exibicao": i, **linha} for i, linha in enumerate(linhas, start=1)
    ]


def montar_cartao(instrumentos: list[dict], barras: list[dict]) -> list[dict]:
    n_inst = len(instrumentos)
    n_explicita = sum(i["explicita_publico_racial"] for i in instrumentos)
    n_nomeado = sum(i["grupo_nomeado"] for i in instrumentos)
    top = barras[0]
    return [{
        "n_instrumentos": n_inst,
        "n_explicitam_publico_racial": n_explicita,
        "pct_explicitam_publico_racial": round(100 * n_explicita / n_inst, 1) if n_inst else 0.0,
        "grupo_mais_citado": top["grupo"],
        "n_grupo_mais_citado": top["n_instrumentos"],
        "n_grupos_distintos": sum(1 for b in barras if b["n_instrumentos"] > 0),
        "n_grupo_nomeado": n_nomeado,
        "pct_grupo_nomeado": round(100 * n_nomeado / n_inst, 1) if n_inst else 0.0,
    }]


# ===========================================================================
# TED
# ===========================================================================
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


def montar_instrumentos_ted(planos: list[dict], resumo: list[dict]) -> list[dict]:
    origem_por_plano = calcular_origem_por_plano(resumo)

    instrumentos = []
    for p in planos:
        if _txt(p.get("tx_situacao_plano_acao")).upper() in SITUACOES_EXCLUIDAS_TED:
            continue

        pid = _txt(p.get("id_plano_acao"))
        cats = classificar(
            p.get("tx_objeto_plano_acao", ""), p.get("tx_justificativa_plano_acao", "")
        )
        instrumentos.append({
            "id": pid,
            "ano": _ano_int(p.get("aa_ano_plano_acao")),
            "origem": origem_por_plano.get(pid, ROTULO_SEM_INFO),
            **cats,
        })
    return instrumentos


def calcular_i3_ted(planos: list[dict], resumo: list[dict]) -> dict[str, list[dict]]:
    """Calcula as três saídas do I3 (TED)."""
    instrumentos = montar_instrumentos_ted(planos, resumo)
    if not instrumentos:
        raise ValueError("Universo vazio: confira as situações excluídas.")

    fato = montar_fato(instrumentos, dims=["ano", "origem"])
    barras = montar_barras(fato, len(instrumentos))
    cartao = montar_cartao(instrumentos, barras)

    assert len(fato) == len(instrumentos) * len(GRUPOS)
    assert sum(b["n_instrumentos"] for b in barras) == sum(f["ativo"] for f in fato)

    return {
        "i3_ted_publico_fato": fato,
        "i3_ted_publico_barras": barras,
        "i3_ted_publico_cartao": cartao,
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
) -> list[dict]:
    instrumentos = []
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
        qualidade = _qualidade_dado(empenhado, pago, firmado)
        if excluir_empenho_zero_com_pago and qualidade == "empenho_zero_com_pagamento":
            continue

        cats = classificar(r.get("objeto", ""))
        instrumentos.append({
            "id": _txt(r.get("nr_convenio")),
            "ano": ano,
            "origem": ROTULO_EMENDA if _txt(r.get("parlamentares")) else ROTULO_REGULAR,
            "modalidade": _txt(r.get("modalidade_instrumento")).title(),
            "qualidade_dado": qualidade,
            **cats,
        })
    return instrumentos


def calcular_i3_convenios(gold: list[dict]) -> dict[str, list[dict]]:
    """Calcula as três saídas do I3 (Convênios/Fomentos)."""
    instrumentos = montar_instrumentos_convenio(gold)
    if not instrumentos:
        raise ValueError("Universo vazio: confira ANO_CORTE_CONVENIO e as situações excluídas.")

    fato = montar_fato(instrumentos, dims=["ano", "origem", "modalidade", "qualidade_dado"])
    barras = montar_barras(fato, len(instrumentos))
    cartao = montar_cartao(instrumentos, barras)

    assert len(fato) == len(instrumentos) * len(GRUPOS)
    assert sum(b["n_instrumentos"] for b in barras) == sum(f["ativo"] for f in fato)

    return {
        "i3_convenio_publico_fato": fato,
        "i3_convenio_publico_barras": barras,
        "i3_convenio_publico_cartao": cartao,
    }


# ===========================================================================
# Orquestração
# ===========================================================================
def calcular_i3(
    planos: list[dict], resumo: list[dict], gold_convenios: list[dict]
) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I3 (TED + Convênios/Fomentos)."""
    return {
        **calcular_i3_ted(planos, resumo),
        **calcular_i3_convenios(gold_convenios),
    }
