"""Indicador I2 — Valor Médio por Executor/Convenente, por UF.

Porte de ``I2/i2_ted_bi.R`` e ``I2/i2_convenios_bi.R`` (equipe de BI, pacote
Bloco 1). Substitui a versão anterior deste indicador (concentração
institucional via HHI, lendo a SAÍDA do I1). Esta versão troca o HHI por
valor médio por entidade (executor/convenente) dentro de cada UF, lendo as
tabelas dbt diretamente — TED e Convênios/Fomentos calculados por módulos
independentes (``calcular_i2_ted`` / ``calcular_i2_convenios``), mesmo
padrão do I1/I3/I4/I8.

O QUE O INDICADOR ENTREGA: barras por UF — valor médio por entidade =
firmado da UF ÷ nº de entidades distintas da UF; linha de referência = média
nacional (firmado total ÷ total de entidades). Ponderação sempre pelo nº de
entidades (nunca média de médias): o grupo "Demais" soma o firmado das UFs
menores e divide pela soma dos seus executores/convenentes.

TED — UF é a SEDE do executor, não o território atendido:
 - Executor = unidade descentralizada do plano (``sigla_unidade_descentralizada``).
   Cada executor pertence a uma única UF (a da sede), via o dicionário
   ``SIGLA_PARA_UF``. Sigla fora do dicionário vira "Sem UF"; plano sem
   sigla é corrigido pelo nome via ``CORRECAO_SIGLA_VAZIA`` quando possível,
   senão vira "Sem sigla".
 - Valor = firmado (``vl_total_plano_acao``), não empenhado — a maioria dos
   TEDs tem empenho zero, o que zeraria a maior parte da carteira.
 - Mesmo universo e lógica de origem do I1/I4/I8 novos.

Convênios/Fomentos — UF é ``uf_execucao`` do gold, DEIXADA EM BRANCO desde o
fix de ``siconv_dbt.resumo_convenios`` (decisão da equipe: não inferir de
outra fonte do SICONV, dado real virá do coleta mir). Na prática, hoje TODO
convênio cai no grupo único "Sem UF" até esse dado existir — o indicador
continua funcionando (não quebra, não é caso especial no código), só não
quebra por UF enquanto a fonte não é populada. Quando o coleta mir existir,
este indicador passa a desagregar por UF sem precisar de nenhuma mudança de
código.
 - Convenente identificado pelo NOME normalizado (sem CNPJ na base) —
   variações de grafia podem inflar a contagem de convenentes.
 - Mesmo universo do I1 Convênios (ano >= 2023, situações excluídas,
   exclusão de ``empenho_zero_com_pagamento`` por padrão).
 - Um convenente pode aparecer em mais de uma UF — conta uma vez em cada UF.

Fontes (tabelas dbt):
    siafi_dbt.planos_acao_ted         → cadastro, firmado, ano, situação, executor
    siafi_dbt.ted_resumo_orcamentario → usado só para a coluna origem
    siconv_dbt.resumo_convenios       → convênios/fomentos consolidados

Saídas (6):
    i2_ted_executor_uf_fato, i2_ted_uf_barras, i2_ted_cartao,
    i2_convenio_convenente_uf_fato, i2_convenio_uf_barras, i2_convenio_cartao
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
N_UFS_DESTAQUE = 8
ROTULO_DEMAIS = "Demais"
ROTULO_SEM_UF = "Sem UF"

# Dicionário sigla do executor -> UF da sede. Acrescentar siglas novas aqui.
SIGLA_PARA_UF = {
    "AGU": "DF", "ABC": "DF", "CAPES": "DF", "CGU": "DF", "CNPq": "DF",
    "CODEVASF": "DF", "CONAB": "DF", "Enap": "DF", "FCP": "DF", "IBGE": "RJ",
    "IPEA": "DF", "MEC": "DF", "MinC": "DF", "SENAD": "DF", "SENATP": "DF",
    "FIOCRUZ": "RJ", "CPAR": "RJ", "IFB": "DF", "IFBA": "BA", "IFG": "GO",
    "IFMA": "MA", "IFRJ": "RJ", "IFRN": "RN", "IFSP": "SP", "UFABC": "SP",
    "UFAL": "AL", "UFBA": "BA", "UFC": "CE", "UFCG": "PB", "UFF": "RJ",
    "UFFS": "SC", "UFG": "GO", "UFGD": "MS", "UFJ": "GO", "UFMA": "MA",
    "UFOPA": "PA", "UFPA": "PA", "UFPB": "PB", "UFRB": "BA", "UFRGS": "RS",
    "UFRJ": "RJ", "UFSB": "BA", "UFSC": "SC", "UFSCar": "SP", "UFSM": "RS",
    "UFU": "MG", "UNB": "DF", "UNIFEI": "MG", "UNIRIO": "RJ", "UNIVASF": "PE",
    "UFCSPA": "RS", "UTFPR": "PR", "UFPR": "PR",
}
# Plano sem sigla de executor: corrige pelo nome da unidade (maiúsculas, sem acento)
CORRECAO_SIGLA_VAZIA = {"UNIVERSIDADE FEDERAL DO PARANA": "UFPR"}


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


def _normalizar_nome(valor: Any) -> str:
    return " ".join(_sem_acento(_txt(valor)).upper().split())


def _limpa_uf(valor: Any) -> str:
    texto = _txt(valor).upper()
    return texto if len(texto) == 2 and texto.isalpha() else ""


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


def _classifica_grupo_uf(
    por_uf: list[dict], n_ufs_destaque: int = N_UFS_DESTAQUE
) -> list[dict]:
    """Marca as N maiores UFs por firmado com uf_grupo=uf; o resto vira 'Demais'."""
    ordenadas = sorted(por_uf, key=lambda l: (-l["firmado"], l["uf"]))
    return [
        {**l, "uf_grupo": l["uf"] if posicao <= n_ufs_destaque else ROTULO_DEMAIS}
        for posicao, l in enumerate(ordenadas, start=1)
    ]


# ===========================================================================
# TED
# ===========================================================================
def montar_fato_ted(planos: list[dict], resumo: list[dict]) -> list[dict]:
    origem_por_plano = calcular_origem_por_plano(resumo)
    correcao = {_normalizar_nome(k): v for k, v in CORRECAO_SIGLA_VAZIA.items()}

    vistos: set[str] = set()
    fato = []
    for p in planos:
        pid = _txt(p.get("id_plano_acao"))
        if not pid or pid in vistos:
            continue
        vistos.add(pid)

        if _txt(p.get("tx_situacao_plano_acao")).upper() in SITUACOES_EXCLUIDAS_TED:
            continue

        sigla = _txt(p.get("sigla_unidade_descentralizada"))
        if not sigla:
            sigla = correcao.get(_normalizar_nome(p.get("unidade_descentralizada")), "")
        executor = sigla or "Sem sigla"
        uf = SIGLA_PARA_UF.get(sigla, ROTULO_SEM_UF) if sigla else ROTULO_SEM_UF

        fato.append({
            "id_plano_acao": pid,
            "executor": executor,
            "uf": uf,
            "ano": _ano_int(p.get("aa_ano_plano_acao")),
            "origem": origem_por_plano.get(pid, ROTULO_SEM_INFO),
            "firmado": round(_num(p.get("vl_total_plano_acao")), 2),
        })
    return fato


def montar_barras_ted(fato: list[dict]) -> list[dict]:
    firm_total = sum(f["firmado"] for f in fato)
    n_exec_total = len({f["executor"] for f in fato})
    media_nacional = round(firm_total / n_exec_total, 2) if n_exec_total else 0.0

    acc: dict[str, dict] = defaultdict(lambda: {"executores": set(), "n_teds": 0, "firmado": 0.0})
    for f in fato:
        a = acc[f["uf"]]
        a["executores"].add(f["executor"])
        a["n_teds"] += 1
        a["firmado"] += f["firmado"]
    por_uf = [
        {"uf": uf, "n_executores": len(v["executores"]), "n_teds": v["n_teds"], "firmado": round(v["firmado"], 2)}
        for uf, v in acc.items()
    ]
    por_uf = _classifica_grupo_uf(por_uf)

    acc_grupo: dict[str, dict] = defaultdict(lambda: {"n_ufs": 0, "n_executores": 0, "n_teds": 0, "firmado": 0.0})
    for l in por_uf:
        g = acc_grupo[l["uf_grupo"]]
        g["n_ufs"] += 1
        g["n_executores"] += l["n_executores"]
        g["n_teds"] += l["n_teds"]
        g["firmado"] += l["firmado"]

    linhas = []
    for uf_grupo, v in acc_grupo.items():
        valor_medio = round(v["firmado"] / v["n_executores"], 2) if v["n_executores"] else 0.0
        linhas.append({
            "uf_grupo": uf_grupo,
            "n_ufs": v["n_ufs"],
            "n_executores": v["n_executores"],
            "n_teds": v["n_teds"],
            "firmado": round(v["firmado"], 2),
            "valor_medio_por_executor": valor_medio,
            "media_nacional": media_nacional,
            "acima_da_media": 1 if valor_medio > media_nacional else 0,
            "grupo_demais": 1 if uf_grupo == ROTULO_DEMAIS else 0,
        })
    linhas.sort(key=lambda l: (l["grupo_demais"], -l["valor_medio_por_executor"]))
    return [{"ordem_exibicao": i, **l} for i, l in enumerate(linhas, start=1)]


def montar_cartao_ted(fato: list[dict]) -> list[dict]:
    n_exec_total = len({f["executor"] for f in fato})
    firm_total = sum(f["firmado"] for f in fato)
    return [{
        "n_executores": n_exec_total,
        "n_teds": len(fato),
        "firmado": round(firm_total, 2),
        "media_nacional": round(firm_total / n_exec_total, 2) if n_exec_total else 0.0,
    }]


def calcular_i2_ted(planos: list[dict], resumo: list[dict]) -> dict[str, list[dict]]:
    """Calcula as três saídas do I2 (TED)."""
    fato = montar_fato_ted(planos, resumo)
    if not fato:
        raise ValueError("Universo vazio: confira as situações excluídas.")

    barras = montar_barras_ted(fato)
    cartao = montar_cartao_ted(fato)

    firm_total = sum(f["firmado"] for f in fato)
    assert abs(sum(b["firmado"] for b in barras) - firm_total) < 0.05
    assert sum(b["n_teds"] for b in barras) == len(fato)

    return {
        "i2_ted_executor_uf_fato": fato,
        "i2_ted_uf_barras": barras,
        "i2_ted_cartao": cartao,
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


def montar_fato_convenio(
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

        instrumentos.append({
            "nr_convenio": _txt(r.get("nr_convenio")),
            "convenente": _normalizar_nome(r.get("nome_convenente")) or "SEM NOME",
            "uf": _limpa_uf(r.get("uf_execucao")) or ROTULO_SEM_UF,
            "categoria_convenente": _txt(r.get("categoria_convenente")) or "Sem categoria",
            "modalidade": _txt(r.get("modalidade_instrumento")).title(),
            "ano": ano,
            "origem": ROTULO_EMENDA if _txt(r.get("parlamentares")) else ROTULO_REGULAR,
            "qualidade_dado": qualidade,
            "firmado": firmado,
        })
    return instrumentos


def montar_fato(instrumentos: list[dict]) -> list[dict]:
    """Agrega o grão de instrumento em (convenente, uf, categoria, ano, origem,
    modalidade, qualidade_dado) — grão do fato gravado."""
    acc: dict[tuple, dict] = defaultdict(lambda: {"n_instrumentos": 0, "firmado": 0.0})
    for i in instrumentos:
        chave = (
            i["convenente"], i["uf"], i["categoria_convenente"], i["ano"],
            i["origem"], i["modalidade"], i["qualidade_dado"],
        )
        a = acc[chave]
        a["n_instrumentos"] += 1
        a["firmado"] += i["firmado"]

    linhas = [
        {
            "convenente": chave[0], "uf": chave[1], "categoria_convenente": chave[2],
            "ano": chave[3], "origem": chave[4], "modalidade": chave[5], "qualidade_dado": chave[6],
            "n_instrumentos": v["n_instrumentos"], "firmado": round(v["firmado"], 2),
        }
        for chave, v in acc.items()
    ]
    linhas.sort(key=lambda l: (l["uf"], l["convenente"], l["ano"] is None, l["ano"], l["origem"], l["modalidade"], l["qualidade_dado"]))
    return linhas


def montar_barras_convenio(instrumentos: list[dict]) -> list[dict]:
    firm_total = sum(i["firmado"] for i in instrumentos)
    n_conv_total = len({i["convenente"] for i in instrumentos})
    media_nacional = round(firm_total / n_conv_total, 2) if n_conv_total else 0.0

    acc: dict[str, dict] = defaultdict(lambda: {"convenentes": set(), "n_instrumentos": 0, "firmado": 0.0})
    for i in instrumentos:
        a = acc[i["uf"]]
        a["convenentes"].add(i["convenente"])
        a["n_instrumentos"] += 1
        a["firmado"] += i["firmado"]
    por_uf = [
        {"uf": uf, "n_convenentes": len(v["convenentes"]), "n_instrumentos": v["n_instrumentos"], "firmado": round(v["firmado"], 2)}
        for uf, v in acc.items()
    ]
    por_uf = _classifica_grupo_uf(por_uf)

    acc_grupo: dict[str, dict] = defaultdict(lambda: {"n_ufs": 0, "n_convenentes": 0, "n_instrumentos": 0, "firmado": 0.0})
    for l in por_uf:
        g = acc_grupo[l["uf_grupo"]]
        g["n_ufs"] += 1
        g["n_convenentes"] += l["n_convenentes"]
        g["n_instrumentos"] += l["n_instrumentos"]
        g["firmado"] += l["firmado"]

    linhas = []
    for uf_grupo, v in acc_grupo.items():
        valor_medio = round(v["firmado"] / v["n_convenentes"], 2) if v["n_convenentes"] else 0.0
        linhas.append({
            "uf_grupo": uf_grupo,
            "n_ufs": v["n_ufs"],
            "n_convenentes": v["n_convenentes"],
            "n_instrumentos": v["n_instrumentos"],
            "firmado": round(v["firmado"], 2),
            "valor_medio_por_convenente": valor_medio,
            "media_nacional": media_nacional,
            "acima_da_media": 1 if valor_medio > media_nacional else 0,
            "grupo_demais": 1 if uf_grupo == ROTULO_DEMAIS else 0,
        })
    linhas.sort(key=lambda l: (l["grupo_demais"], -l["valor_medio_por_convenente"]))
    return [{"ordem_exibicao": i, **l} for i, l in enumerate(linhas, start=1)]


def montar_cartao_convenio(instrumentos: list[dict]) -> list[dict]:
    n_conv_total = len({i["convenente"] for i in instrumentos})
    firm_total = sum(i["firmado"] for i in instrumentos)
    return [{
        "n_convenentes": n_conv_total,
        "n_instrumentos": len(instrumentos),
        "firmado": round(firm_total, 2),
        "media_nacional": round(firm_total / n_conv_total, 2) if n_conv_total else 0.0,
    }]


def calcular_i2_convenios(gold: list[dict]) -> dict[str, list[dict]]:
    """Calcula as três saídas do I2 (Convênios/Fomentos)."""
    instrumentos = montar_fato_convenio(gold)
    if not instrumentos:
        raise ValueError("Universo vazio: confira ANO_CORTE_CONVENIO e as situações excluídas.")

    fato = montar_fato(instrumentos)
    barras = montar_barras_convenio(instrumentos)
    cartao = montar_cartao_convenio(instrumentos)

    firm_total = sum(i["firmado"] for i in instrumentos)
    assert abs(sum(b["firmado"] for b in barras) - firm_total) < 0.05
    assert abs(sum(f["firmado"] for f in fato) - firm_total) < 0.05
    assert sum(b["n_instrumentos"] for b in barras) == len(instrumentos)

    return {
        "i2_convenio_convenente_uf_fato": fato,
        "i2_convenio_uf_barras": barras,
        "i2_convenio_cartao": cartao,
    }


# ===========================================================================
# Orquestração
# ===========================================================================
def calcular_i2(
    planos: list[dict], resumo: list[dict], gold_convenios: list[dict]
) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I2 (TED + Convênios/Fomentos)."""
    return {
        **calcular_i2_ted(planos, resumo),
        **calcular_i2_convenios(gold_convenios),
    }
