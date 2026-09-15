"""Indicador I2 — Concentração Institucional dos Executores.

Porte de ``i2_concentracao_executores.py`` (TED) e
``i2_concentracao_executores_convenios.py`` (Convênios/Fomentos), equipe de
BI. Funções puras — a lógica e as decisões metodológicas são as dos scripts
originais; só a origem dos dados muda.

Diferente do I1, este indicador NÃO reprocessa as tabelas dbt: ele lê a SAÍDA
do I1 já gravada no schema ``indicadores`` (``i1_ted_por_instrumento`` e
``i1_convenios_por_instrumento``), decisão da BI para os dois indicadores
nunca divergirem sobre "quem está no universo". A DAG deste indicador roda
por isso depois da DAG do I1.

Fontes (tabelas em ``indicadores``, gravadas pela DAG do I1):
    indicadores.i1_ted_por_instrumento       → universo + valores dos TEDs
    indicadores.i1_convenios_por_instrumento → universo + valores dos
                                                convênios/fomentos

Decisões metodológicas (resumo; detalhe nos scripts originais):
 1. Leitura institucional, não territorial: a UF do TED é a SEDE do executor
    (dicionário ``SIGLA_PARA_UF``, por sigla institucional), não o território
    atendido — um TED com sede em Brasília pode financiar o país inteiro.
    Convênios usam ``uf_execucao`` (execução real, já validada no I1).
 2. Base do HHI difere por fonte: TED usa ``vl_firmado`` (92 dos 116 TEDs têm
    empenho zero — HHI sobre empenhado zeraria a participação da maior parte
    da carteira); Convênios usa ``empenhado_liquido`` (só 11 de 181 têm
    empenho zero).
 3. Tipo institucional (TED): classificação por correspondência EXATA de
    sigla (não por prefixo, para não confundir UNIFEI/UNIRIO/UNIVASF com
    universidades federais "UF*"). "Outro" é honesto, não substantivo —
    mistura naturezas jurídicas diferentes (autarquia, fundação, órgão etc).
 4. Sigla vazia (TED): corrigida via nome do executor quando possível (ex.:
    "UNIVERSIDADE FEDERAL DO PARANA" -> "UFPR"); senão vira "SEM_SIGLA".
 5. Convênios: agregação por NOME do convenente (``gold_convenios`` não tem
    CNPJ) — risco de variação de grafia inflar a contagem de executores
    distintos, registrado como limitação, não resolvido aqui.
 6. Convênios: um mesmo convenente pode executar em mais de uma UF (ao
    contrário do TED, onde a sede é fixa) — o agregado por executor não
    atribui UF única, reporta ``n_ufs_distintas``.
 7. HHI = Σ (participação percentual de cada executor)², em escala 0-10.000.
    Calculado sobre os valores SEM arredondamento intermediário (arredondar
    cada share antes de somar os quadrados desloca o HHI final).
"""

from collections import defaultdict
from typing import Any


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


# ---------------------------------------------------------------------------
# Dicionário sigla -> UF-sede e tipo institucional (decisões 1/3/4; TED)
# ---------------------------------------------------------------------------
SIGLA_PARA_UF = {
    "AGU": "DF", "CAPES": "DF", "CGU": "DF", "CNPq": "DF", "CODEVASF": "DF",
    "CONAB": "DF", "Enap": "DF", "FCP": "DF", "IBGE": "RJ", "IPEA": "DF",
    "MEC": "DF", "MinC": "DF", "SENAD": "DF", "SENATP": "DF",
    "FIOCRUZ": "RJ",
    "CPAR": "RJ", "IFB": "DF", "IFBA": "BA", "IFG": "GO", "IFMA": "MA",
    "IFRJ": "RJ", "IFRN": "RN", "IFSP": "SP",
    "UFABC": "SP", "UFAL": "AL", "UFBA": "BA", "UFC": "CE", "UFCG": "PB",
    "UFF": "RJ", "UFFS": "SC", "UFG": "GO", "UFGD": "MS", "UFJ": "GO",
    "UFMA": "MA", "UFOPA": "PA", "UFPA": "PA", "UFPB": "PB", "UFRB": "BA",
    "UFRGS": "RS", "UFRJ": "RJ", "UFSB": "BA", "UFSC": "SC", "UFSCar": "SP",
    "UFSM": "RS", "UFU": "MG", "UNB": "DF", "UNIFEI": "MG", "UNIRIO": "RJ",
    "UNIVASF": "PE", "UFCSPA": "RS", "UTFPR": "PR",
    "UFPR": "PR",  # decisão 4: inferido para TEDs sem sigla preenchida
}

UNIVERSIDADES_FEDERAIS = {
    "UFABC", "UFAL", "UFBA", "UFC", "UFCG", "UFCSPA", "UFF", "UFFS", "UFG",
    "UFGD", "UFJ", "UFMA", "UFOPA", "UFPA", "UFPB", "UFPR", "UFRB", "UFRGS",
    "UFRJ", "UFSB", "UFSC", "UFSCar", "UFSM", "UFU", "UNB", "UNIFEI",
    "UNIRIO", "UNIVASF", "UTFPR",
}
INSTITUTOS_FEDERAIS = {"IFB", "IFBA", "IFG", "IFMA", "IFRJ", "IFRN", "IFSP", "CPAR"}

# Decisão 4: sigla vazia -> inferida pelo nome do executor
CORRECAO_SIGLA_VAZIA = {
    "UNIVERSIDADE FEDERAL DO PARANA": "UFPR",
}


def _tipo_institucional(sigla: str) -> str:
    if sigla in UNIVERSIDADES_FEDERAIS:
        return "Universidade Federal"
    if sigla in INSTITUTOS_FEDERAIS:
        return "Instituto Federal"
    return "Outro"


def _hhi_por_grupo(linhas: list[dict], chave: str, campo_valor: str) -> float:
    """HHI = Σ (share_pct)², sem arredondar cada share antes de somar (decisão 7)."""
    total = sum(_num(l[campo_valor]) for l in linhas)
    if not total:
        return 0.0
    somas: dict[str, float] = defaultdict(float)
    for l in linhas:
        somas[l[chave]] += _num(l[campo_valor])
    return round(sum((soma / total * 100) ** 2 for soma in somas.values()), 1)


# ---------------------------------------------------------------------------
# Bloco 1 — TED
# ---------------------------------------------------------------------------
def calcular_ted_localizacao_institucional(teds_i1: list[dict]) -> list[dict]:
    """Enriquece o universo do I1 (TED) com UF-sede e tipo institucional."""
    linhas = []
    for t in teds_i1:
        sigla = _txt(t.get("sigla_executor"))
        if not sigla:
            nome = _txt(t.get("nome_executor")).upper()
            sigla = CORRECAO_SIGLA_VAZIA.get(nome, "") or "SEM_SIGLA"

        linhas.append({
            "id_plano_acao": _txt(t.get("id_plano_acao")),
            "sigla_executor": sigla,
            "nome_executor": _txt(t.get("nome_executor")),
            "uf_sede": SIGLA_PARA_UF.get(sigla, "NAO_MAPEADO"),
            "tipo_institucional": _tipo_institucional(sigla),
            "programa_governo": _txt(t.get("programa_governo")),
            "origem": _txt(t.get("origem")),
            "ano": _txt(t.get("ano")),
            "vl_firmado": round(_num(t.get("vl_firmado")), 2),
        })
    return linhas


def agregar_ted_por_executor(localizacao: list[dict]) -> list[dict]:
    """Agrega por executor; HHI sobre vl_firmado (decisão 2)."""
    total = sum(l["vl_firmado"] for l in localizacao)
    acc: dict[str, dict] = defaultdict(lambda: {
        "nome_executor": "", "uf_sede": "", "tipo_institucional": "",
        "n_teds": 0, "vl_firmado": 0.0,
    })
    for l in localizacao:
        e = acc[l["sigla_executor"]]
        e["nome_executor"] = l["nome_executor"]
        e["uf_sede"] = l["uf_sede"]
        e["tipo_institucional"] = l["tipo_institucional"]
        e["n_teds"] += 1
        e["vl_firmado"] += l["vl_firmado"]

    saida = []
    for sigla, v in sorted(acc.items(), key=lambda x: -x[1]["vl_firmado"]):
        share_pct_raw = v["vl_firmado"] / total * 100 if total else 0.0
        saida.append({
            "sigla_executor": sigla,
            "nome_executor": v["nome_executor"],
            "uf_sede": v["uf_sede"],
            "tipo_institucional": v["tipo_institucional"],
            "n_teds": v["n_teds"],
            "vl_firmado": round(v["vl_firmado"], 2),
            "share_pct": round(share_pct_raw, 2),
            "share_pct_ao_quadrado": round(share_pct_raw ** 2, 2),
        })
    return saida


def calcular_resumo_ted(localizacao: list[dict]) -> list[dict]:
    return [{
        "n_teds": len(localizacao),
        "n_executores_distintos": len({l["sigla_executor"] for l in localizacao}),
        "total_firmado": round(sum(l["vl_firmado"] for l in localizacao), 2),
        "hhi": _hhi_por_grupo(localizacao, "sigla_executor", "vl_firmado"),
    }]


# ---------------------------------------------------------------------------
# Bloco 2 — Convênios/Fomentos
# ---------------------------------------------------------------------------
def calcular_convenio_localizacao_institucional(convenios_i1: list[dict]) -> list[dict]:
    """Recorta do universo do I1 (Convênios) os campos usados por este indicador."""
    return [
        {
            "nr_convenio": _txt(c.get("nr_convenio")),
            "convenente": _txt(c.get("convenente")),
            "categoria_convenente": _txt(c.get("categoria_convenente")),
            "uf_execucao": _txt(c.get("uf_execucao")),
            "municipio_execucao": _txt(c.get("municipio_execucao")),
            "instrumento": _txt(c.get("instrumento")),
            "origem": _txt(c.get("origem")),
            "ano": _txt(c.get("ano")),
            "empenhado_liquido": round(_num(c.get("empenhado_liquido")), 2),
        }
        for c in convenios_i1
    ]


def agregar_convenio_por_executor(localizacao: list[dict]) -> list[dict]:
    """Agrega por convenente (nome); HHI sobre empenhado_liquido (decisão 2).

    Sem UF única por executor (decisão 6): reporta n_ufs_distintas.
    """
    total = sum(l["empenhado_liquido"] for l in localizacao)
    acc: dict[str, dict] = defaultdict(lambda: {
        "categoria_convenente": "", "n_instrumentos": 0,
        "empenhado_liquido": 0.0, "ufs": set(),
    })
    for l in localizacao:
        e = acc[l["convenente"]]
        e["categoria_convenente"] = l["categoria_convenente"] or e["categoria_convenente"]
        e["n_instrumentos"] += 1
        e["empenhado_liquido"] += l["empenhado_liquido"]
        if l["uf_execucao"]:
            e["ufs"].add(l["uf_execucao"])

    saida = []
    for convenente, v in sorted(acc.items(), key=lambda x: -x[1]["empenhado_liquido"]):
        share_pct_raw = v["empenhado_liquido"] / total * 100 if total else 0.0
        saida.append({
            "convenente": convenente,
            "categoria_convenente": v["categoria_convenente"],
            "n_instrumentos": v["n_instrumentos"],
            "n_ufs_distintas": len(v["ufs"]),
            "empenhado_liquido": round(v["empenhado_liquido"], 2),
            "share_pct": round(share_pct_raw, 2),
            "share_pct_ao_quadrado": round(share_pct_raw ** 2, 2),
        })
    return saida


def calcular_resumo_convenio(localizacao: list[dict]) -> list[dict]:
    return [{
        "n_instrumentos": len(localizacao),
        "n_convenentes_distintos": len({l["convenente"] for l in localizacao}),
        "total_empenhado": round(sum(l["empenhado_liquido"] for l in localizacao), 2),
        "hhi": _hhi_por_grupo(localizacao, "convenente", "empenhado_liquido"),
    }]


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def calcular_i2(teds_i1: list[dict], convenios_i1: list[dict]) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I2 a partir da saída do I1."""
    loc_ted = calcular_ted_localizacao_institucional(teds_i1)
    loc_conv = calcular_convenio_localizacao_institucional(convenios_i1)
    return {
        "i2_ted_localizacao_institucional": loc_ted,
        "i2_executores_concentracao": agregar_ted_por_executor(loc_ted),
        "i2_resumo": calcular_resumo_ted(loc_ted),
        "i2_convenio_localizacao_institucional": loc_conv,
        "i2_convenio_concentracao": agregar_convenio_por_executor(loc_conv),
        "i2_resumo_convenio": calcular_resumo_convenio(loc_conv),
    }
