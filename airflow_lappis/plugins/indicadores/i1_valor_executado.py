"""Indicador I1 — Valor Executado por Instrumento.

Porte de ``i1_valor_executado.py`` e ``i1_etapa_cadeia_ted.R`` (equipe de BI,
2026-07-21) para funções puras. A lógica e as decisões metodológicas são as
do script original; os dados vêm dos data marts ``mir_teds`` e
``mir_convenios`` (remodelagem fato-dimensão do dbt MIR, etapa 5).

    Leitura 1 — valor por instrumento (TED + convênio + fomento), SEM território
    Leitura 2 — valor por território (UF e município), SOMENTE convênios/fomentos

Fontes (tabelas do dbt):
    mir_teds.dim_plano_acao              → cadastro dos TEDs e origem do recurso
    mir_teds.fato_plano_acao_posicao     → valores por TED e quantidades de PF/NC/NE
    mir_teds.fato_execucao_orcamentaria  → NEs por TED (programa de governo)
    mir_teds.dim_acao_orcamentaria       → programa de cada PTRES
    mir_convenios.dim_convenio           → cadastro dos convênios/fomentos
    mir_convenios.fato_convenio_posicao  → valores por convênio
    mir_convenios.dim_convenente         → convenente
    mir_convenios.dim_localidade         → UF e município de execução

As dimensões se ligam às posições pelas chaves ``sk_*``; o membro ``-1``
("Não identificado") das dimensões não entra no universo.

Decisões metodológicas (resumo; o detalhe está no script original):
 1. Duas leituras separadas: TED fica FORA da leitura territorial, porque a
    única UF disponível é a sede do executor, não o território atendido.
 2. Convênios vêm de fato_convenio_posicao (grão: um instrumento por linha).
    O tipo é a ``modalidade``, a origem é ``origem_recurso`` (Emenda quando
    alguma NE do instrumento é de emenda) e o empenhado é o registrado no
    SICONV (``valor_empenhado_siconv``, a mesma medida do gold antigo).
 3. Universo dos convênios: ano >= 2023 (data_assinatura, fallback
    data_inicio_vigencia); excluídos Cancelado/Anulado; empenhado zero
    permanece na contagem, marcado em ``sem_empenho``.
 4. Universo dos TEDs: todos os planos exceto REJEITADO. As flags
    ``execucao_*`` desagregam, não filtram.
 5. Empenhado do TED vem da posição do plano: bruto, anulado e líquido já
    consolidam todas as NEs ligadas ao plano.
 6. Origem do TED: ``origem_recurso`` da dim_plano_acao.
 7. Etapa da cadeia sob a Definição B (TED = flag descentralizada OU tem NC),
    pelas quantidades de PF, NC e NE da posição; TEDs fora dela ficam com
    ``etapa_cadeia`` vazia.
 8. Programa de governo do TED: o programa com maior empenhado nas NEs do
    plano (empate: menor código); vazio se o plano não tem NE.
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Callable, Iterable

ANO_CORTE = 2023
SITUACOES_EXCLUIDAS_CONVENIO = {"Cancelado", "Convênio Anulado", "Convenio Anulado"}
SITUACOES_EXCLUIDAS_TED = {"REJEITADO"}
FLAGS_VERDADEIRAS = {"SIM", "TRUE", "S", "1"}
ROTULO_NAO_INFORMADO = "NAO_INFORMADO"
MEMBRO_NAO_IDENTIFICADO = "-1"
ORIGEM_EMENDA = "Emenda"


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


def _flag(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    return _txt(valor).upper() in FLAGS_VERDADEIRAS


def _ano(valor: Any) -> int | None:
    if isinstance(valor, (date, datetime)):
        return valor.year
    texto = _txt(valor)
    if len(texto) >= 4 and texto[:4].isdigit():
        return int(texto[:4])
    return None


def _share(parte: float, total: float) -> float:
    return round(parte / total * 100, 2) if total else 0


def _por_chave(linhas: Iterable[dict], campo: str) -> dict[Any, dict]:
    return {r.get(campo): r for r in linhas}


def _membros(linhas: Iterable[dict], campo_sk: str) -> list[dict]:
    """Linhas da dimensão sem o membro -1 (Não identificado)."""
    return [r for r in linhas if _txt(r.get(campo_sk)) != MEMBRO_NAO_IDENTIFICADO]


def _origem(linha: dict) -> str:
    if _txt(linha.get("origem_recurso")) == ORIGEM_EMENDA:
        return "emenda"
    return "orcamento_regular"


# ---------------------------------------------------------------------------
# Etapa da cadeia (Definição B) — porte de i1_etapa_cadeia_ted.R
# ---------------------------------------------------------------------------
def classificar_etapa_cadeia(
    planos: list[dict], posicao_planos: list[dict]
) -> dict[str, str]:
    """Estágio no funil PF → NC → NE por TED, sob a Definição B.

    Universo: plano com flag ``execucao_descentralizada`` OU com NC na
    posição. Retorna ``{id_plano_acao: estagio}``.
    """
    posicao = _por_chave(posicao_planos, "sk_plano_acao")

    etapas: dict[str, str] = {}
    for p in _membros(planos, "sk_plano_acao"):
        pid = _txt(p.get("id_plano_acao"))
        pos = posicao.get(p.get("sk_plano_acao"), {})
        tem_pf = _num(pos.get("qtd_pf")) > 0
        tem_nc = _num(pos.get("qtd_nc")) > 0
        tem_ne = _num(pos.get("qtd_nes")) > 0
        if not (_flag(p.get("execucao_descentralizada")) or tem_nc):
            continue
        if tem_pf and tem_nc and tem_ne:
            etapas[pid] = "S4_cadeia_plena"
        elif tem_pf and tem_nc:
            etapas[pid] = "S3_ate_NC"
        elif tem_pf:
            etapas[pid] = "S2_ate_PF"
        elif tem_nc:
            etapas[pid] = "S3_NC_sem_PF"
        else:
            etapas[pid] = "S1_so_plano"
    return etapas


# ---------------------------------------------------------------------------
# Bloco 1 — TEDs: valor por instrumento, SEM território
# ---------------------------------------------------------------------------
def _programa_por_plano(
    execucao_teds: list[dict], acoes_teds: list[dict]
) -> dict[Any, str]:
    """Programa de governo com maior empenhado nas NEs de cada plano."""
    programa_da_acao = {
        a.get("sk_acao_orcamentaria"): _txt(a.get("codigo_programa")) for a in acoes_teds
    }
    empenhado: dict[tuple, float] = defaultdict(float)
    for r in execucao_teds:
        programa = programa_da_acao.get(r.get("sk_acao_orcamentaria"), "")
        if programa:
            chave = (r.get("sk_plano_acao"), programa)
            empenhado[chave] += _num(r.get("despesas_empenhadas"))

    escolhido: dict[Any, str] = {}
    for (sk_plano, programa), _valor in sorted(
        empenhado.items(), key=lambda x: (-x[1], x[0][1])
    ):
        escolhido.setdefault(sk_plano, programa)
    return escolhido


def calcular_teds(
    planos: list[dict],
    posicao_planos: list[dict],
    execucao_teds: list[dict],
    acoes_teds: list[dict],
    etapa_por_plano: dict[str, str] | None = None,
) -> list[dict]:
    etapa_por_plano = etapa_por_plano or {}
    posicao = _por_chave(posicao_planos, "sk_plano_acao")
    programa_por_plano = _programa_por_plano(execucao_teds, acoes_teds)

    teds = []
    for p in _membros(planos, "sk_plano_acao"):
        situacao = _txt(p.get("situacao"))
        if situacao in SITUACOES_EXCLUIDAS_TED:
            continue

        sk = p.get("sk_plano_acao")
        pid = _txt(p.get("id_plano_acao"))
        pos = posicao.get(sk, {})

        empenhado = _num(pos.get("empenhado_bruto"))
        anulado = _num(pos.get("empenho_anulado"))
        pago = _num(pos.get("despesas_pagas")) + _num(pos.get("restos_a_pagar_pagos"))
        formas = [
            nome
            for nome, campo in (
                ("direta", "execucao_direta"),
                ("particulares", "execucao_particulares"),
                ("descentralizada", "execucao_descentralizada"),
            )
            if _flag(p.get(campo))
        ]

        teds.append({
            "id_plano_acao": pid,
            "sq_instrumento": _txt(p.get("num_transf")),
            "instrumento": "TED",
            "origem": _origem(p),
            "ano": _txt(p.get("ano")),
            "situacao": situacao,
            "sigla_executor": _txt(p.get("sigla_unidade_descentralizada")),
            "nome_executor": _txt(p.get("unidade_descentralizada")),
            "programa_governo": programa_por_plano.get(sk, ""),
            "etapa_cadeia": etapa_por_plano.get(pid, ""),
            "forma_execucao_2n": "; ".join(formas),
            "vl_firmado": round(_num(pos.get("valor_firmado")), 2),
            "empenhado_bruto": round(empenhado, 2),
            "empenho_anulado": round(anulado, 2),
            "empenhado_liquido": round(empenhado - anulado, 2),
            "liquidado": round(_num(pos.get("despesas_liquidadas")), 2),
            "pago": round(pago, 2),
            "qtd_nes": int(_num(pos.get("qtd_nes"))),
        })
    return teds


def agregar_teds_por_executor(teds: list[dict]) -> list[dict]:
    total = sum(t["empenhado_liquido"] for t in teds)
    acc: dict[str, dict] = defaultdict(lambda: {
        "nome_executor": "", "n_teds": 0, "n_sem_empenho": 0,
        "vl_firmado": 0.0, "empenhado_liquido": 0.0, "pago": 0.0,
    })
    for t in teds:
        e = acc[t["sigla_executor"]]
        e["nome_executor"] = t["nome_executor"]
        e["n_teds"] += 1
        e["n_sem_empenho"] += 1 if t["empenhado_liquido"] == 0 else 0
        e["vl_firmado"] += t["vl_firmado"]
        e["empenhado_liquido"] += t["empenhado_liquido"]
        e["pago"] += t["pago"]

    return [
        {
            "sigla_executor": sigla,
            "nome_executor": v["nome_executor"],
            "n_teds": v["n_teds"],
            "n_sem_empenho": v["n_sem_empenho"],
            "vl_firmado": round(v["vl_firmado"], 2),
            "empenhado_liquido": round(v["empenhado_liquido"], 2),
            "pago": round(v["pago"], 2),
            "share_pct": _share(v["empenhado_liquido"], total),
        }
        for sigla, v in sorted(acc.items(), key=lambda x: -x[1]["empenhado_liquido"])
    ]


# ---------------------------------------------------------------------------
# Bloco 2 — Convênios e termos: valor + território real
# ---------------------------------------------------------------------------
def _ano_instrumento(r: dict) -> tuple[int | None, str | None]:
    """Ano de referência: data_assinatura, com fallback para o início da vigência."""
    for campo, rotulo in (
        ("data_assinatura", "data_assinatura"),
        ("data_inicio_vigencia", "inicio_vigencia"),
    ):
        ano = _ano(r.get(campo))
        if ano is not None:
            return ano, rotulo
    return None, None


def calcular_convenios(
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
    localidades: list[dict],
    ano_corte: int = ANO_CORTE,
) -> list[dict]:
    posicao = _por_chave(posicao_convenios, "sk_convenio")
    convenente_por_sk = _por_chave(convenentes, "sk_convenente")
    localidade_por_sk = _por_chave(localidades, "sk_localidade")

    saida = []
    for r in _membros(convenios, "sk_convenio"):
        ano, ano_fonte = _ano_instrumento(r)
        if ano is None or ano < ano_corte:
            continue
        situacao = _txt(r.get("situacao"))
        if situacao in SITUACOES_EXCLUIDAS_CONVENIO:
            continue

        pos = posicao.get(r.get("sk_convenio"), {})
        convenente = convenente_por_sk.get(pos.get("sk_convenente"), {})
        localidade = localidade_por_sk.get(pos.get("sk_localidade"), {})
        empenhado = _num(pos.get("valor_empenhado_siconv"))
        saida.append({
            "nr_convenio": _txt(r.get("nr_convenio")),
            "instrumento": _txt(r.get("modalidade")),
            "origem": _origem(r),
            "ano": ano,
            "ano_fonte": ano_fonte,
            "situacao": situacao,
            "uf_execucao": _txt(localidade.get("uf")),
            "municipio_execucao": _txt(localidade.get("municipio")),
            "convenente": _txt(convenente.get("convenente_nome")),
            "categoria_convenente": _txt(convenente.get("convenente_natureza_juridica")),
            "vl_firmado": round(_num(pos.get("valor_firmado_atualizado")), 2),
            "empenhado_liquido": round(empenhado, 2),
            "pago": round(_num(pos.get("valor_pago_fornecedores")), 2),
            "sem_empenho": 1 if empenhado == 0 else 0,
        })
    return saida


def _agregar_territorio(
    convenios: list[dict],
    chave: Callable[[dict], tuple],
    nomes_chave: list[str],
) -> list[dict]:
    """Agrega convênios por chave territorial, com share DENTRO do bloco.

    Município e UF saem em colunas separadas para desambiguar homônimos.
    """
    total = sum(c["empenhado_liquido"] for c in convenios)
    acc: dict[tuple, dict] = defaultdict(lambda: {
        "n_instrumentos": 0, "n_sem_empenho": 0, "n_emenda": 0, "n_regular": 0,
        "vl_firmado": 0.0, "empenhado_liquido": 0.0, "pago": 0.0,
    })
    for c in convenios:
        a = acc[chave(c)]
        a["n_instrumentos"] += 1
        a["n_sem_empenho"] += c["sem_empenho"]
        a["n_emenda"] += 1 if c["origem"] == "emenda" else 0
        a["n_regular"] += 1 if c["origem"] == "orcamento_regular" else 0
        a["vl_firmado"] += c["vl_firmado"]
        a["empenhado_liquido"] += c["empenhado_liquido"]
        a["pago"] += c["pago"]

    saida = []
    for k, v in sorted(acc.items(), key=lambda x: -x[1]["empenhado_liquido"]):
        linha = dict(zip(nomes_chave, k))
        linha.update({
            "n_instrumentos": v["n_instrumentos"],
            "n_sem_empenho": v["n_sem_empenho"],
            "n_emenda": v["n_emenda"],
            "n_regular": v["n_regular"],
            "vl_firmado": round(v["vl_firmado"], 2),
            "empenhado_liquido": round(v["empenhado_liquido"], 2),
            "pago": round(v["pago"], 2),
            "share_pct": _share(v["empenhado_liquido"], total),
        })
        saida.append(linha)
    return saida


def agregar_convenios_por_uf(convenios: list[dict]) -> list[dict]:
    return _agregar_territorio(
        convenios,
        lambda c: (c["uf_execucao"] or ROTULO_NAO_INFORMADO,),
        ["uf_execucao"],
    )


def agregar_convenios_por_municipio(convenios: list[dict]) -> list[dict]:
    return _agregar_territorio(
        convenios,
        lambda c: (
            c["municipio_execucao"] or ROTULO_NAO_INFORMADO,
            c["uf_execucao"] or ROTULO_NAO_INFORMADO,
        ),
        ["municipio_execucao", "uf_execucao"],
    )


# ---------------------------------------------------------------------------
# Leitura 1 — carteira por tipo de instrumento e origem (SEM território)
# ---------------------------------------------------------------------------
def calcular_carteira(teds: list[dict], convenios: list[dict]) -> list[dict]:
    acc: dict[tuple, dict] = defaultdict(lambda: {
        "n_instrumentos": 0, "n_sem_empenho": 0,
        "vl_firmado": 0.0, "empenhado_liquido": 0.0, "pago": 0.0,
    })
    for item in [*teds, *convenios]:
        c = acc[(item["instrumento"], item["origem"])]
        c["n_instrumentos"] += 1
        c["n_sem_empenho"] += 1 if item["empenhado_liquido"] == 0 else 0
        c["vl_firmado"] += item["vl_firmado"]
        c["empenhado_liquido"] += item["empenhado_liquido"]
        c["pago"] += item["pago"]

    total = sum(v["empenhado_liquido"] for v in acc.values())
    return [
        {
            "instrumento": instrumento,
            "origem": origem,
            "n_instrumentos": v["n_instrumentos"],
            "n_sem_empenho": v["n_sem_empenho"],
            "vl_firmado": round(v["vl_firmado"], 2),
            "empenhado_liquido": round(v["empenhado_liquido"], 2),
            "pago": round(v["pago"], 2),
            "share_pct": _share(v["empenhado_liquido"], total),
            "leitura": "carteira_sem_territorio",
        }
        for (instrumento, origem), v in sorted(
            acc.items(), key=lambda x: -x[1]["empenhado_liquido"]
        )
    ]


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def calcular_i1(
    planos: list[dict],
    posicao_planos: list[dict],
    execucao_teds: list[dict],
    acoes_teds: list[dict],
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
    localidades: list[dict],
) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I1 a partir das tabelas dos marts."""
    etapas = classificar_etapa_cadeia(planos, posicao_planos)
    teds = calcular_teds(planos, posicao_planos, execucao_teds, acoes_teds, etapas)
    convenios_i1 = calcular_convenios(
        convenios, posicao_convenios, convenentes, localidades
    )
    return {
        "i1_ted_por_instrumento": teds,
        "i1_ted_por_executor": agregar_teds_por_executor(teds),
        "i1_convenios_por_instrumento": convenios_i1,
        "i1_convenios_por_uf": agregar_convenios_por_uf(convenios_i1),
        "i1_convenios_por_municipio": agregar_convenios_por_municipio(convenios_i1),
        "i1_valor_por_instrumento": calcular_carteira(teds, convenios_i1),
    }
