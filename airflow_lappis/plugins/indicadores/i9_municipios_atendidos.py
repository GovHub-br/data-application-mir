"""Indicador I9 — Municípios Atendidos (Convênios/Fomentos).

Porte de ``i9_municipios_atendidos_convenios.py`` (equipe de BI). Só existe
para Convênios/Fomentos — não se aplica ao TED, cujo único campo de
município na Fase 1 registra a sede do executor (concentração artificial em
Brasília), não o local de execução real (decisão da BI, ver docstring do
script original).

Diferente do I3/I7, este indicador NÃO reprocessa tabelas dbt: lê a SAÍDA do
I1 já gravada no schema ``indicadores`` (``i1_convenios_por_municipio``),
mesma decisão do I2, para nunca divergir do universo do I1.

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
    Nº de municípios distintos com execução (``municipio_execucao`` !=
    "NAO_INFORMADO", rótulo do I1 para ausência).
    Cobertura (%) = (municípios atendidos ÷ total de municípios) × 100.
"""

from collections import Counter
from typing import Any

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

ROTULO_NAO_INFORMADO = "NAO_INFORMADO"


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


def _municipios_atendidos(convenios_por_municipio: list[dict]) -> list[dict]:
    return [
        m for m in convenios_por_municipio
        if _txt(m.get("municipio_execucao")) != ROTULO_NAO_INFORMADO
    ]


def calcular_cobertura_nacional(convenios_por_municipio: list[dict]) -> list[dict]:
    atendidos = _municipios_atendidos(convenios_por_municipio)
    n_atendidos = len(atendidos)
    return [{
        "municipios_atendidos": n_atendidos,
        "total_municipios_brasil": TOTAL_MUNICIPIOS_BRASIL,
        "cobertura_pct": round(n_atendidos / TOTAL_MUNICIPIOS_BRASIL * 100, 2),
        "n_instrumentos": int(sum(_num(m.get("n_instrumentos")) for m in atendidos)),
    }]


def calcular_cobertura_uf(convenios_por_municipio: list[dict]) -> list[dict]:
    atendidos = _municipios_atendidos(convenios_por_municipio)

    por_uf: Counter = Counter()
    instr_por_uf: Counter = Counter()
    for m in atendidos:
        uf = _txt(m.get("uf_execucao"))
        por_uf[uf] += 1
        instr_por_uf[uf] += int(_num(m.get("n_instrumentos")))

    linhas = []
    for uf, municipios_atendidos_uf in sorted(por_uf.items(), key=lambda x: -x[1]):
        total_uf = TOTAL_MUNICIPIOS_POR_UF.get(uf, 0)
        linhas.append({
            "uf": uf,
            "municipios_atendidos": municipios_atendidos_uf,
            "total_municipios_uf": total_uf,
            "cobertura_pct": (
                round(municipios_atendidos_uf / total_uf * 100, 2) if total_uf else ""
            ),
            "n_instrumentos": instr_por_uf[uf],
        })
    return linhas


def calcular_i9(convenios_por_municipio: list[dict]) -> dict[str, list[dict]]:
    """Calcula as duas saídas do I9 a partir da saída do I1."""
    return {
        "i9_convenio_cobertura_nacional": calcular_cobertura_nacional(
            convenios_por_municipio
        ),
        "i9_convenio_cobertura_uf": calcular_cobertura_uf(convenios_por_municipio),
    }
