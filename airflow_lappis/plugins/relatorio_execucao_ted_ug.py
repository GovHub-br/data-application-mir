import codecs
import csv
import logging
import re
from typing import Any, Dict, List

import chardet

# Relatório "Execução TED por UG" do Tesouro Gerencial: execução do crédito
# descentralizado pelo MIR (destaque recebido) nas UGs executoras de outros órgãos,
# no grão ano x órgão x UG x ação x PO x PTRES x grupo x fonte. É a consulta
# oficial do MIR para o gasto com TEDs. Métrica "Saldo - R$": cada linha é a
# posição acumulada do ano até a data da extração.
#
# Layout (separado por tabulação): três linhas de título herdadas de um modelo
# antigo, cabeçalho, uma linha de subcabeçalho e os dados. Código e nome vêm em
# colunas vizinhas; o Tesouro intercala linhas "Total" por UG (coluna da ação) e
# por ano (coluna do órgão), que não são dado.

HEADER_MARKER = '"Ano Lançamento"'

COLUMNS: List[str] = [
    "ano_lancamento",  # 0
    "orgao_uge_codigo",  # 1
    "orgao_uge_nome",  # 2
    "ug_executora_codigo",  # 3
    "ug_executora_nome",  # 4
    "acao_governo_codigo",  # 5
    "acao_governo_nome",  # 6
    "plano_orcamentario_codigo",  # 7
    "plano_orcamentario_nome",  # 8
    "ptres",  # 9
    "grupo_despesa",  # 10
    "fonte_recursos_detalhada",  # 11
    "destaque_recebido",  # 12
    "credito_disponivel",  # 13
    "despesas_empenhadas",  # 14
    "despesas_liquidadas",  # 15
    "despesas_pagas",  # 16
]

# Rótulo esperado no cabeçalho (e, para a fonte, no subcabeçalho) por posição:
# se o relatório mudar de layout, o mapeamento por posição gravaria colunas
# deslocadas, então a carga falha antes.
HEADER_LABELS: Dict[int, str] = {
    0: "Ano Lançamento",
    1: "Órgão UGE",
    3: "UG Executora",
    5: "Ação Governo",
    7: "Plano Orçamentário",
    9: "PTRES",
    10: "Grupo Despesa",
    12: "DESTAQUE RECEBIDO",
    13: "CREDITO DISPONIVEL",
    14: "DESPESAS EMPENHADAS",
    15: "DESPESAS LIQUIDADAS",
    16: "DESPESAS PAGAS",
}
SUB_HEADER_LABELS: Dict[int, str] = {11: "Fonte Recursos Detalhada"}


def decodificar(raw: bytes) -> str:
    """Texto do CSV do anexo. O Tesouro manda este relatório em UTF-16 com BOM;
    sem BOM, a codificação é detectada (latin-1 se a detecção falhar)."""
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig", errors="replace")
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16", errors="replace")
    encoding = chardet.detect(raw)["encoding"] or "latin-1"
    return raw.decode(encoding, errors="replace")


def _check_labels(row: List[str], labels: Dict[int, str], linha: str) -> None:
    for pos, esperado in labels.items():
        achado = row[pos].strip() if pos < len(row) else None
        if achado != esperado:
            raise ValueError(
                f"Layout do relatório 'Execução TED por UG' mudou: no {linha}, "
                f"esperava '{esperado}' na posição {pos}, achou '{achado}'."
            )


def parse_execucao_ted_ug(csv_data: str) -> List[Dict[str, Any]]:
    """Linhas de dado do relatório, como texto (None para vazio), sem as linhas
    de título e de total. Levanta ValueError se o cabeçalho não for o esperado."""
    lines = csv_data.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.lstrip().startswith(HEADER_MARKER)),
        None,
    )
    if header_idx is None or header_idx + 1 >= len(lines):
        raise ValueError(
            "Cabeçalho do relatório 'Execução TED por UG' não encontrado: esperava "
            f"uma linha começando com {HEADER_MARKER}."
        )
    _check_labels(
        next(csv.reader([lines[header_idx]], delimiter="\t")), HEADER_LABELS, "cabeçalho"
    )
    _check_labels(
        next(csv.reader([lines[header_idx + 1]], delimiter="\t")),
        SUB_HEADER_LABELS,
        "subcabeçalho",
    )

    records: List[Dict[str, Any]] = []
    totais = descartadas = 0
    for line in lines[header_idx + 2 :]:
        if not line.strip():
            continue
        row = next(csv.reader([line], delimiter="\t"))
        if not row or not re.fullmatch(r"\d{4}", row[0].strip()):
            descartadas += 1
            continue
        if "Total" in (row[1].strip(), row[5].strip() if len(row) > 5 else ""):
            totais += 1
            continue
        if len(row) != len(COLUMNS):
            descartadas += 1
            continue
        records.append({c: (v.strip() or None) for c, v in zip(COLUMNS, row)})

    if descartadas:
        logging.warning(
            "[relatorio_execucao_ted_ug.py] %s linha(s) descartada(s) por formato "
            "inesperado.",
            descartadas,
        )
    logging.info(
        "[relatorio_execucao_ted_ug.py] %s linhas de dado, %s linhas de total "
        "ignoradas.",
        len(records),
        totais,
    )
    return records
