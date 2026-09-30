"""Indicador I3 — Instrumentos com Público-Alvo Racializado.

Porte de ``i3_publico_alvo.py`` (equipe de BI, idêntico nas pastas TED e
Convênios — é um único script que processa as duas fontes). Função pura — a
lógica e as decisões metodológicas são as do script original; só a origem
dos dados muda (tabelas dbt no lugar dos CSVs exportados para o OneDrive).

Diferente do I2, este indicador NÃO lê a saída do I1: reprocessa as mesmas
tabelas-fonte do I1 (mesmo universo e filtros), porque precisa do texto do
objeto/justificativa, que a saída do I1 não carrega.

Fontes (tabelas dos marts, as mesmas do I1):
    mir_teds.dim_plano_acao              → objeto, justificativa e origem do TED
    mir_teds.fato_credito_descentralizado → NCs por TED (programa de governo)
    mir_teds.dim_acao_orcamentaria       → programa de cada PTRES
    mir_convenios.dim_convenio           → objeto, modalidade e origem do convênio
    mir_convenios.fato_convenio_posicao  → liga o convênio ao convenente
    mir_convenios.dim_convenente         → nome do convenente

O membro -1 ("Não identificado") das dimensões não entra no universo. O
programa de governo do TED usa a regra do I1 (programa_por_plano_ted).

AVISO DE VALIDAÇÃO: ao contrário do I1 e do I2, este módulo não foi validado
por regressão ponta-a-ponta contra dado real — os textos de objeto/
justificativa que alimentam a classificação não estavam disponíveis no
ambiente de porte (só os CSVs de saída já processados pela BI, sem o texto
de entrada). A lógica de classificação foi portada byte a byte do script
original; a validação real fica para a execução da DAG contra o Postgres,
onde dá pra conferir números de checagem que a própria BI registrou (ex.:
22 dos 118 TEDs mencionam "cigan*", majoritariamente via a sigla SQPT).

Decisões metodológicas (resumo; o detalhe está no script original):
 1. Categoria "ciganos" existe e não é marginal (confirmado pela BI: 22 dos
    118 TEDs, 6 convênios/fomentos).
 2. Duas leituras: ESTRITA (categoria específica nomeada — é o indicador
    reportado) e AMPLA (estrita OU racial_generico). O gap entre as duas é
    a "oportunidade de amadurecimento" na ficha do sumário.
 3. Método é só busca textual (regex) sobre texto normalizado (minúsculas,
    sem acento). Sem camada de similaridade semântica/embeddings — limitação
    conhecida, não implementada aqui.
 4. Mesmo universo e filtros do I1: TEDs excluem situação REJEITADO;
    Convênios usam o mesmo corte de ano (>=2023) e exclusão de situação
    (Cancelado/Convênio Anulado) do I1.
 5. Convênios não têm campo de programa de governo estruturado — só TED tem
    essa desagregação.
 6. Subcategorias informativas dentro de "pessoas_negras": mulheres_negras e
    estudantes_negros. Não alteram leitura_estrita — são subconjunto.
"""

import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Iterable

from indicadores.i1_valor_executado import programa_por_plano_ted

ANO_CORTE = 2023
SITUACOES_EXCLUIDAS_CONVENIO = {"Cancelado", "Convênio Anulado", "Convenio Anulado"}
SITUACOES_EXCLUIDAS_TED = {"REJEITADO"}
GRUPOS = ["pessoas_negras", "quilombolas", "indigenas", "terreiro", "ciganos"]
MEMBRO_NAO_IDENTIFICADO = "-1"
ORIGEM_EMENDA = "Emenda"


# ---------------------------------------------------------------------------
# Normalização (mesmos helpers do i1_valor_executado.py)
# ---------------------------------------------------------------------------
def _txt(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _ano(valor: Any) -> int | None:
    if isinstance(valor, (date, datetime)):
        return valor.year
    texto = _txt(valor)
    if len(texto) >= 4 and texto[:4].isdigit():
        return int(texto[:4])
    return None


def _ano_instrumento(r: dict) -> int | None:
    """Ano de referência: data_assinatura, com fallback para o início da vigência."""
    for campo in ("data_assinatura", "data_inicio_vigencia"):
        ano = _ano(r.get(campo))
        if ano is not None:
            return ano
    return None


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
# Padrões de classificação (aplicados sobre texto em minúsculas, sem acento)
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Minúsculas + remove acentos, para facilitar o casamento de regex."""
    texto = (texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


CATEGORIAS = {
    "pessoas_negras": re.compile(
        r"negr[ao]|negras|negros|afro.brasileir|afrodescendent|"
        r"\bpret[ao]\b|pretas|pretos|"
        r"pessoas negras|populacao negra|mulheres negras|jovens negros|"
        r"homens negros|criancas negras|idosos negros",
        re.IGNORECASE,
    ),
    "quilombolas": re.compile(r"quilombol", re.IGNORECASE),
    "indigenas": re.compile(
        r"ind[ií]gen|povos origin[aá]rios|comunidades indigenas", re.IGNORECASE
    ),
    "terreiro": re.compile(
        r"terreiro|matriz africana|candombl[eé]|umbanda|"
        r"povos de terreiro|comunidades de terreiro|religiosidade afro",
        re.IGNORECASE,
    ),
    # Decisão 1: categoria confirmada nos dados, majoritariamente via SQPT.
    "ciganos": re.compile(r"cigan", re.IGNORECASE),
    "racial_generico": re.compile(
        r"igualdade racial|antirracist|[eé]tnico.racial|etnico.racial|"
        r"relacoes etnico|relações étnico|acoes afirmativas|ações afirmativas|"
        r"enfrentamento ao racismo|promocao da igualdade",
        re.IGNORECASE,
    ),
}
CATEGORIAS_ESPECIFICAS = [
    "pessoas_negras", "quilombolas", "indigenas", "terreiro", "ciganos",
]

# Decisão 6: subcategorias informativas, subconjunto de pessoas_negras
SUBCATEGORIAS = {
    "mulheres_negras": re.compile(r"mulheres negras|mulher negra", re.IGNORECASE),
    "estudantes_negros": re.compile(
        r"estudantes negr|aluno[as]? negr|estudante negr", re.IGNORECASE
    ),
}


def classificar(*textos: str) -> dict[str, int]:
    """Classifica um instrumento nas categorias raciais (decisão 2)."""
    texto = normalizar(" ".join(t or "" for t in textos))
    resultado: dict[str, int] = {}
    for categoria, padrao in CATEGORIAS.items():
        resultado[categoria] = 1 if padrao.search(texto) else 0
    for sub, padrao in SUBCATEGORIAS.items():
        resultado[sub] = 1 if padrao.search(texto) else 0

    resultado["leitura_estrita"] = (
        1 if any(resultado[c] for c in CATEGORIAS_ESPECIFICAS) else 0
    )
    resultado["leitura_ampla"] = (
        1 if (resultado["leitura_estrita"] or resultado["racial_generico"]) else 0
    )
    return resultado


# ---------------------------------------------------------------------------
# Bloco 1 — TEDs
# ---------------------------------------------------------------------------
def montar_instrumentos_ted(
    planos: list[dict], creditos_teds: list[dict], acoes_teds: list[dict]
) -> list[dict]:
    programa_por_plano = programa_por_plano_ted(creditos_teds, acoes_teds)

    instrumentos = []
    for p in _membros(planos, "sk_plano_acao"):
        if _txt(p.get("situacao")) in SITUACOES_EXCLUIDAS_TED:
            continue

        cats = classificar(p.get("objeto") or "", p.get("justificativa") or "")
        instrumentos.append({
            "tipo": "TED",
            "instrumento": "TED",
            "id_instrumento": _txt(p.get("id_plano_acao")),
            "origem": _origem(p),
            "ano": _txt(p.get("ano")),
            "programa_governo": programa_por_plano.get(p.get("sk_plano_acao"), ""),
            "sigla_executor": _txt(p.get("sigla_unidade_descentralizada")),
            "tx_objeto": _txt(p.get("objeto"))[:200],
            **cats,
        })
    return instrumentos


# ---------------------------------------------------------------------------
# Bloco 2 — Convênios e Termos (mesmo universo do I1)
# ---------------------------------------------------------------------------
def montar_instrumentos_convenio(
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
    ano_corte: int = ANO_CORTE,
) -> list[dict]:
    posicao = _por_chave(posicao_convenios, "sk_convenio")
    convenente_por_sk = _por_chave(
        _membros(convenentes, "sk_convenente"), "sk_convenente"
    )

    instrumentos = []
    for r in _membros(convenios, "sk_convenio"):
        ano = _ano_instrumento(r)
        if ano is None or ano < ano_corte:
            continue
        if _txt(r.get("situacao")) in SITUACOES_EXCLUIDAS_CONVENIO:
            continue

        pos = posicao.get(r.get("sk_convenio"), {})
        convenente = convenente_por_sk.get(pos.get("sk_convenente"), {})
        cats = classificar(r.get("objeto") or "")
        instrumentos.append({
            "tipo": "Convenio_Fomento",
            "instrumento": _txt(r.get("modalidade")),
            "id_instrumento": _txt(r.get("nr_convenio")),
            "origem": _origem(r),
            "ano": ano,
            "programa_governo": "",  # convênio não tem programa estruturado (decisão 5)
            "sigla_executor": _txt(convenente.get("convenente_nome")),
            "tx_objeto": _txt(r.get("objeto"))[:200],
            **cats,
        })
    return instrumentos


# ---------------------------------------------------------------------------
# Formato longo, para Power BI (unpivot por grupo)
# ---------------------------------------------------------------------------
def _montar_grupos(
    instrumentos: list[dict], id_campo: str, campo_extra: str
) -> list[dict]:
    return [
        {
            id_campo: r["id_instrumento"],
            "grupo": grupo,
            "ativo": r[grupo],
            "leitura_estrita": r["leitura_estrita"],
            "leitura_ampla": r["leitura_ampla"],
            "racial_generico": r["racial_generico"],
            campo_extra: r[campo_extra],
            "origem": r["origem"],
            "ano": r["ano"],
        }
        for r in instrumentos
        for grupo in GRUPOS
    ]


def montar_grupos_ted(instrumentos_ted: list[dict]) -> list[dict]:
    return _montar_grupos(instrumentos_ted, "id_plano_acao", "programa_governo")


def montar_grupos_convenio(instrumentos_convenio: list[dict]) -> list[dict]:
    return _montar_grupos(instrumentos_convenio, "nr_convenio", "instrumento")


# ---------------------------------------------------------------------------
# Resumo por bloco (TED, Convênio/Fomento, TOTAL, e por modalidade)
# ---------------------------------------------------------------------------
def _resumo_bloco(bloco: list[dict], tipo: str) -> dict:
    total = len(bloco)
    n_estrita = sum(r["leitura_estrita"] for r in bloco)
    n_ampla = sum(r["leitura_ampla"] for r in bloco)
    return {
        "tipo": tipo,
        "total_instrumentos": total,
        "leitura_estrita_n": n_estrita,
        "leitura_estrita_pct": round(100 * n_estrita / total, 1) if total else 0,
        "leitura_ampla_n": n_ampla,
        "leitura_ampla_pct": round(100 * n_ampla / total, 1) if total else 0,
        "gap_leitura_pct": round(100 * (n_ampla - n_estrita) / total, 1) if total else 0,
        "pessoas_negras": sum(r["pessoas_negras"] for r in bloco),
        "mulheres_negras": sum(r["mulheres_negras"] for r in bloco),
        "estudantes_negros": sum(r["estudantes_negros"] for r in bloco),
        "quilombolas": sum(r["quilombolas"] for r in bloco),
        "indigenas": sum(r["indigenas"] for r in bloco),
        "terreiro": sum(r["terreiro"] for r in bloco),
        "ciganos": sum(r["ciganos"] for r in bloco),
        "racial_generico_apenas": sum(
            1 for r in bloco if r["racial_generico"] and not r["leitura_estrita"]
        ),
        "sem_mencao_racial": sum(1 for r in bloco if not r["leitura_ampla"]),
    }


def calcular_resumo(instrumentos: list[dict]) -> list[dict]:
    teds = [r for r in instrumentos if r["tipo"] == "TED"]
    convenios = [r for r in instrumentos if r["tipo"] == "Convenio_Fomento"]

    linhas = [
        _resumo_bloco(teds, "TED"),
        _resumo_bloco(convenios, "Convenio_Fomento"),
        _resumo_bloco(instrumentos, "TOTAL"),
    ]

    por_instrumento: dict[str, list[dict]] = defaultdict(list)
    for r in instrumentos:
        por_instrumento[r["instrumento"]].append(r)
    for instr, bloco in sorted(por_instrumento.items()):
        if instr == "TED":
            continue  # já coberto na linha "TED" acima
        linhas.append(_resumo_bloco(bloco, instr))
    return linhas


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def calcular_i3(
    planos: list[dict],
    creditos_teds: list[dict],
    acoes_teds: list[dict],
    convenios: list[dict],
    posicao_convenios: list[dict],
    convenentes: list[dict],
) -> dict[str, list[dict]]:
    """Calcula as quatro saídas do I3 a partir das tabelas dos marts."""
    instrumentos_ted = montar_instrumentos_ted(planos, creditos_teds, acoes_teds)
    instrumentos_convenio = montar_instrumentos_convenio(
        convenios, posicao_convenios, convenentes
    )
    todos = instrumentos_ted + instrumentos_convenio
    return {
        "i3_publico_alvo_instrumentos": todos,
        "i3_publico_alvo_resumo": calcular_resumo(todos),
        "i3_ted_publico_alvo_grupos": montar_grupos_ted(instrumentos_ted),
        "i3_convenio_publico_alvo_grupos": montar_grupos_convenio(instrumentos_convenio),
    }
