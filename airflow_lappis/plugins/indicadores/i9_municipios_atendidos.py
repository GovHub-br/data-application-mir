"""Indicador I9 — Municípios Atendidos (Convênios/Fomentos).

Porte de ``i9_municipios_atendidos_convenios.py`` (equipe de BI). Só existe
para Convênios/Fomentos — não se aplica ao TED, cujo único campo de
município na Fase 1 registra a sede do executor (concentração artificial em
Brasília), não o local de execução real (decisão da BI, ver docstring do
script original).

FONTE DO MUNICÍPIO (mudou com o Bloco 1): o script original lia a saída
``i1_convenios_por_municipio`` do I1 antigo, que agregava por
``resumo_convenios.municipio_execucao``. Duas mudanças tiraram essa base:
o I1 do Bloco 1 (``PR #85``) deixou de ter território, que foi para o I1b, e
o ``PR #80`` deixou ``uf_execucao``/``municipio_execucao`` em branco na gold,
porque eram a sede do proponente com nome de "execução". Este módulo passa
a ler as mesmas fontes dbt do I1b e a aplicar a mesma regra de território do
I1b, só que no grão de município:
 1. "meta" — município(s) da(s) meta(s) física(s) em
    ``convenio_meta_crono_fisico`` (``municipio_meta`` + ``uf_meta``).
 2. "sede" — sem meta com município, usa ``municipio_execucao`` +
    ``uf_execucao`` da gold. Em branco desde o #80, então hoje esse ramo
    nunca é alcançado (igual ao I1b).
 Sem nenhuma das duas, o instrumento não atende município conhecido e fica
 fora da contagem (o antigo "NAO_INFORMADO").

Diferença em relação ao I1b: instrumento com metas em mais de um município
conta em todos eles. O I1b junta esses casos em "Múltiplas UFs" porque não
há base para repartir valor; aqui não se reparte nada, só se conta presença.

UNIVERSO: o do I1 Convênios (``montar_instrumentos_convenio`` do
``i1_valor_executado.py``, importado em vez de copiado), para nunca divergir
dele nem do I1b, que replica o mesmo universo.

DECISÃO DE ARQUITETURA (cadastro IBGE): o script original lia um cache local
(``Dados_Apoio/ibge_municipios.json``) para saber o total de municípios por
UF — esse cache não existe no projeto. Como é dado de referência estático
(a divisão político-administrativa do Brasil não muda com frequência), a
tabela ``TOTAL_MUNICIPIOS_POR_UF`` abaixo foi buscada e conferida contra
fontes públicas (IBGE, via Wikipédia — ver PR #TODO para os links), não
inventada. Dois valores exigiram checagem cruzada por terem saído
inconsistentes entre fontes na primeira busca: Pernambuco (185, não 184 —
uma fonte havia duplicado por engano o valor do Ceará) e Mato Grosso (142).
A soma dos 26 estados bate exatamente com os 5.570 que a própria BI usa
como total nacional (``TOTAL_MUNICIPIOS_BRASIL``, valor citado na ficha do
sumário) — essa batida exata foi o critério de aceite da tabela.

O Distrito Federal entra com 1 (Brasília, contada como unidade estatística
equivalente a município pelo IBGE) — não por lógica própria: a primeira
versão deste módulo excluía o DF por ele não ser dividido em municípios
"de verdade" (Regiões Administrativas), mas isso divergiu do dado real da
BI (`total_municipios_uf=1`, `cobertura_pct=100%` para o DF em
`i9_convenio_cobertura_uf.csv`) na validação por regressão. Corrigido para
bater com o comportamento real do script original.

FÓRMULA:
    Nº de municípios distintos (nome sem acento + UF) com ao menos um
    instrumento do universo.
    Cobertura (%) = (municípios atendidos ÷ total de municípios) × 100.
    ``n_instrumentos`` = instrumentos distintos que atendem ao menos um
    município (do Brasil ou da UF).

Fontes (tabelas dbt):
    siconv_dbt.resumo_convenios            → gold_convenios (universo)
    siconv_dbt.convenio_meta_crono_fisico  → metas físicas (município)

Saídas (2, nome e colunas fixos: vão para a pasta Indicadores do Power BI):
    i9_convenio_cobertura_nacional, i9_convenio_cobertura_uf
"""

import unicodedata
from collections import defaultdict
from typing import Any

from indicadores.i1_valor_executado import montar_instrumentos_convenio

TOTAL_MUNICIPIOS_BRASIL = 5570  # valor citado na ficha do sumário (igual ao original)

# Total de municípios por UF (IBGE). Soma dos 26 estados = 5.570 (bate com
# TOTAL_MUNICIPIOS_BRASIL); DF = 1 (Brasília, ver docstring do módulo).
TOTAL_MUNICIPIOS_POR_UF = {
    "MG": 853, "SP": 645, "RS": 497, "BA": 417, "PR": 399, "SC": 295,
    "GO": 246, "PI": 224, "PB": 223, "MA": 217, "PE": 185, "CE": 184,
    "RN": 167, "PA": 144, "MT": 142, "TO": 139, "AL": 102, "RJ": 92,
    "MS": 79, "ES": 78, "SE": 75, "AM": 62, "RO": 52, "AC": 22, "AP": 16,
    "RR": 15, "DF": 1,
}


def _txt(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _limpa_uf(valor: Any) -> str:
    texto = _txt(valor).upper()
    return texto if len(texto) == 2 and texto.isalpha() else ""


def _chave_municipio(valor: Any) -> str:
    """Nome sem acento, em caixa alta e com espaços simples."""
    texto = unicodedata.normalize("NFD", _txt(valor))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return " ".join(texto.upper().split())


def montar_municipios_metas(meta_crono_fisico: list[dict]) -> dict[str, set[tuple]]:
    """{nr_convenio: {(municipio, uf)}} das metas com município e UF válidos."""
    municipios: dict[str, set[tuple]] = defaultdict(set)
    for m in meta_crono_fisico:
        nr = _txt(m.get("nr_convenio"))
        municipio = _chave_municipio(m.get("municipio_meta"))
        uf = _limpa_uf(m.get("uf_meta"))
        if nr and municipio and uf:
            municipios[nr].add((municipio, uf))
    return dict(municipios)


def localizar_municipios(
    gold_convenios: list[dict], meta_crono_fisico: list[dict]
) -> list[dict]:
    """Uma linha por (instrumento do universo do I1, município atendido)."""
    instrumentos, _ = montar_instrumentos_convenio(gold_convenios)
    if not instrumentos:
        raise ValueError("Universo vazio: confira o universo do I1 Convênios.")

    gold_por_nr = {_txt(r.get("nr_convenio")): r for r in gold_convenios}
    municipios_metas = montar_municipios_metas(meta_crono_fisico)

    localizacoes = []
    for i in instrumentos:
        nr = i["nr_convenio"]
        municipios, fonte = municipios_metas.get(nr, set()), "meta"
        if not municipios:
            gold = gold_por_nr.get(nr, {})
            municipio = _chave_municipio(gold.get("municipio_execucao"))
            uf = _limpa_uf(gold.get("uf_execucao"))
            municipios = {(municipio, uf)} if municipio and uf else set()
            fonte = "sede"
        for municipio, uf in sorted(municipios):
            localizacoes.append({
                "nr_convenio": nr,
                "municipio": municipio,
                "uf": uf,
                "fonte_municipio": fonte,
            })
    return localizacoes


def calcular_cobertura_nacional(localizacoes: list[dict]) -> list[dict]:
    municipios = {(loc["municipio"], loc["uf"]) for loc in localizacoes}
    instrumentos = {loc["nr_convenio"] for loc in localizacoes}
    return [{
        "municipios_atendidos": len(municipios),
        "total_municipios_brasil": TOTAL_MUNICIPIOS_BRASIL,
        "cobertura_pct": round(len(municipios) / TOTAL_MUNICIPIOS_BRASIL * 100, 2),
        "n_instrumentos": len(instrumentos),
    }]


def calcular_cobertura_uf(localizacoes: list[dict]) -> list[dict]:
    municipios_por_uf: dict[str, set] = defaultdict(set)
    instrumentos_por_uf: dict[str, set] = defaultdict(set)
    for loc in localizacoes:
        municipios_por_uf[loc["uf"]].add(loc["municipio"])
        instrumentos_por_uf[loc["uf"]].add(loc["nr_convenio"])

    linhas = []
    for uf, municipios in sorted(
        municipios_por_uf.items(), key=lambda x: (-len(x[1]), x[0])
    ):
        total_uf = TOTAL_MUNICIPIOS_POR_UF.get(uf, 0)
        linhas.append({
            "uf": uf,
            "municipios_atendidos": len(municipios),
            "total_municipios_uf": total_uf,
            "cobertura_pct": (
                round(len(municipios) / total_uf * 100, 2) if total_uf else ""
            ),
            "n_instrumentos": len(instrumentos_por_uf[uf]),
        })
    return linhas


def calcular_i9(
    gold_convenios: list[dict], meta_crono_fisico: list[dict]
) -> dict[str, list[dict]]:
    """Calcula as duas saídas do I9 a partir das tabelas dbt de convênios."""
    localizacoes = localizar_municipios(gold_convenios, meta_crono_fisico)
    return {
        "i9_convenio_cobertura_nacional": calcular_cobertura_nacional(localizacoes),
        "i9_convenio_cobertura_uf": calcular_cobertura_uf(localizacoes),
    }
