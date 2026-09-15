"""Indicador I1 — Valor Executado por Instrumento.

Porte de ``i1_valor_executado.py`` e ``i1_etapa_cadeia_ted.R`` (equipe de BI,
2026-07-21) para funções puras. A lógica e as decisões metodológicas são as
do script original; só a origem dos dados muda (tabelas dbt no lugar dos CSVs
exportados para o OneDrive).

    Leitura 1 — valor por instrumento (TED + convênio + fomento), SEM território
    Leitura 2 — valor por território (UF e município), SOMENTE convênios/fomentos

Fontes (tabelas do dbt):
    siafi_dbt.planos_acao_ted           → cadastro dos TEDs
    siafi_dbt.ted_resumo_orcamentario   → valores financeiros por TED
    siafi_dbt.pf_unificado_planos_acao  → PF por plano (etapa da cadeia)
    siafi_dbt.nc_plano_acao             → NC por plano (etapa da cadeia)
    siafi_dbt.ted_empenhos_plano_acao   → NE por plano (etapa da cadeia)
    siconv_dbt.resumo_convenios         → convênios/fomentos consolidados
    emendas.instrumentos_emendas        → marcação de origem emenda do TED

Decisões metodológicas (resumo; o detalhe está no script original):
 1. Duas leituras separadas: TED fica FORA da leitura territorial, porque a
    única UF disponível é a sede do executor, não o território atendido.
 2. Convênios vêm de resumo_convenios (grão: um instrumento por linha). O tipo
    é ``modalidade_instrumento``, a origem é ``parlamentares`` preenchido e
    ``valor_empenhado`` já é consolidado (não há coluna de anulação).
 3. Universo dos convênios: ano >= 2023 (data_assinatura, fallback
    inicio_vigencia); excluídos Cancelado/Anulado; empenhado zero permanece
    na contagem, marcado em ``sem_empenho``.
 4. Universo dos TEDs: todos os planos exceto REJEITADO. As flags
    ``in_forma_execucao_*`` desagregam, não filtram.
 5. Empenhado líquido do TED = SOMA das linhas do resumo por plano (várias
    ``num_transf`` do mesmo plano não são versões — não deduplicar).
 6. Origem do TED marcada no grão de instrumento via instrumentos_emendas.
 7. Etapa da cadeia sob a Definição B (TED = flag descentralizada OU tem NC),
    universo diferente do I1: TEDs fora dela ficam com ``etapa_cadeia`` vazia.
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Callable, Iterable

ANO_CORTE = 2023
SITUACOES_EXCLUIDAS_CONVENIO = {"Cancelado", "Convênio Anulado", "Convenio Anulado"}
SITUACOES_EXCLUIDAS_TED = {"REJEITADO"}
FLAGS_VERDADEIRAS = {"SIM", "TRUE", "S", "1"}
ROTULO_NAO_INFORMADO = "NAO_INFORMADO"


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


def _ids(linhas: Iterable[dict], campo: str) -> set[str]:
    return {_txt(r.get(campo)) for r in linhas if _txt(r.get(campo))}


# ---------------------------------------------------------------------------
# Etapa da cadeia (Definição B) — porte de i1_etapa_cadeia_ted.R
# ---------------------------------------------------------------------------
def classificar_etapa_cadeia(
    planos: list[dict], pf: list[dict], nc: list[dict], ne: list[dict]
) -> dict[str, str]:
    """Estágio no funil PF → NC → NE por TED, sob a Definição B.

    Universo: plano com flag ``in_forma_execucao_descentralizada`` OU que
    aparece em nc_plano_acao. Retorna ``{id_plano_acao: estagio}``.
    """
    ids_pf = _ids(pf, "id_plano_acao")
    ids_nc = _ids(nc, "id_plano_acao")
    ids_ne = _ids(ne, "plano_acao")

    etapas: dict[str, str] = {}
    for p in planos:
        pid = _txt(p.get("id_plano_acao"))
        if not (_flag(p.get("in_forma_execucao_descentralizada")) or pid in ids_nc):
            continue
        tem_pf, tem_nc, tem_ne = pid in ids_pf, pid in ids_nc, pid in ids_ne
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
def calcular_teds(
    planos: list[dict],
    resumo: list[dict],
    instrumentos_emendas: list[dict],
    etapa_por_plano: dict[str, str] | None = None,
) -> list[dict]:
    etapa_por_plano = etapa_por_plano or {}

    teds_de_emenda = {
        _txt(r.get("numero_instrumento"))
        for r in instrumentos_emendas
        if _txt(r.get("tipo_instrumento")).upper() == "TED"
        and _txt(r.get("numero_instrumento"))
    }

    fin_por_plano: dict[str, list[dict]] = defaultdict(list)
    for r in resumo:
        chave = _txt(r.get("plano_acao"))
        if chave:
            fin_por_plano[chave].append(r)

    teds = []
    for p in planos:
        situacao = _txt(p.get("tx_situacao_plano_acao"))
        if situacao in SITUACOES_EXCLUIDAS_TED:
            continue

        pid = _txt(p.get("id_plano_acao"))
        sq = _txt(p.get("sq_instrumento"))
        linhas = fin_por_plano.get(pid, [])

        empenhado = sum(_num(r.get("empenhado")) for r in linhas)
        anulado = sum(_num(r.get("empenho_anulado")) for r in linhas)
        liquidado = sum(_num(r.get("despesas_liquidada")) for r in linhas)
        pago = sum(
            _num(r.get("despesas_pagas_exercicio")) + _num(r.get("despesas_pagas_rap"))
            for r in linhas
        )
        programas = (_txt(r.get("programa_governo")) for r in linhas)
        programa = next((prog for prog in programas if prog), "")
        formas = [
            nome
            for nome, campo in (
                ("direta", "in_forma_execucao_direta"),
                ("particulares", "in_forma_execucao_particulares"),
                ("descentralizada", "in_forma_execucao_descentralizada"),
            )
            if _flag(p.get(campo))
        ]

        teds.append({
            "id_plano_acao": pid,
            "sq_instrumento": sq,
            "instrumento": "TED",
            "origem": "emenda" if sq in teds_de_emenda else "orcamento_regular",
            "ano": _txt(p.get("aa_ano_plano_acao")),
            "situacao": situacao,
            "sigla_executor": _txt(p.get("sigla_unidade_descentralizada")),
            "nome_executor": _txt(p.get("unidade_descentralizada")),
            "programa_governo": programa,
            "etapa_cadeia": etapa_por_plano.get(pid, ""),
            "forma_execucao_2n": "; ".join(formas),
            "vl_firmado": round(_num(p.get("vl_total_plano_acao")), 2),
            "empenhado_bruto": round(empenhado, 2),
            "empenho_anulado": round(anulado, 2),
            "empenhado_liquido": round(empenhado - anulado, 2),
            "liquidado": round(liquidado, 2),
            "pago": round(pago, 2),
            "n_linhas_resumo": len(linhas),
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
    """Ano de referência: data_assinatura, com fallback para inicio_vigencia."""
    for campo in ("data_assinatura", "inicio_vigencia"):
        ano = _ano(r.get(campo))
        if ano is not None:
            return ano, campo
    return None, None


def calcular_convenios(
    gold_convenios: list[dict], ano_corte: int = ANO_CORTE
) -> list[dict]:
    convenios = []
    for r in gold_convenios:
        ano, ano_fonte = _ano_instrumento(r)
        if ano is None or ano < ano_corte:
            continue
        situacao = _txt(r.get("situacao_atual"))
        if situacao in SITUACOES_EXCLUIDAS_CONVENIO:
            continue

        empenhado = _num(r.get("valor_empenhado"))
        convenios.append({
            "nr_convenio": _txt(r.get("nr_convenio")),
            "instrumento": _txt(r.get("modalidade_instrumento")),
            "origem": "emenda" if _txt(r.get("parlamentares")) else "orcamento_regular",
            "ano": ano,
            "ano_fonte": ano_fonte,
            "situacao": situacao,
            "uf_execucao": _txt(r.get("uf_execucao")),
            "municipio_execucao": _txt(r.get("municipio_execucao")),
            "convenente": _txt(r.get("nome_convenente")),
            "categoria_convenente": _txt(r.get("categoria_convenente")),
            "vl_firmado": round(_num(r.get("valor_firmado_atualizado")), 2),
            "empenhado_liquido": round(empenhado, 2),
            "pago": round(_num(r.get("valor_total_pago")), 2),
            "sem_empenho": 1 if empenhado == 0 else 0,
        })
    return convenios


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
    resumo: list[dict],
    instrumentos_emendas: list[dict],
    gold_convenios: list[dict],
    pf: list[dict],
    nc: list[dict],
    ne: list[dict],
) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I1 a partir das tabelas-fonte."""
    etapas = classificar_etapa_cadeia(planos, pf, nc, ne)
    teds = calcular_teds(planos, resumo, instrumentos_emendas, etapas)
    convenios = calcular_convenios(gold_convenios)
    return {
        "i1_ted_por_instrumento": teds,
        "i1_ted_por_executor": agregar_teds_por_executor(teds),
        "i1_convenios_por_instrumento": convenios,
        "i1_convenios_por_uf": agregar_convenios_por_uf(convenios),
        "i1_convenios_por_municipio": agregar_convenios_por_municipio(convenios),
        "i1_valor_por_instrumento": calcular_carteira(teds, convenios),
    }
