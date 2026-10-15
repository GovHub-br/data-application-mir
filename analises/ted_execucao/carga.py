"""Leitura dos CSVs do Tesouro Gerencial (raiz do repo) e das tabelas exportadas do DW."""

import csv
import io
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

AQUI = Path(__file__).resolve().parent
# CSVs do Tesouro Gerencial: raiz do repositório por padrão (não são versionados)
REPO = os.environ.get("TED_CSV_DIR", str(AQUI.parents[1])) + "/"
DADOS = str(AQUI / "dados") + "/"
SAIDA = str(AQUI / "saida") + "/"
os.makedirs(SAIDA, exist_ok=True)
K = ["ano", "ug", "acao", "po", "ptres", "fonte", "grupo"]


def num(s: str | None) -> float:
    s = (s or "").strip()
    # o relatório em R$ traz o negativo entre parênteses
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    v = float(s.replace(".", "").replace(",", ".")) if s else 0.0
    return -v if neg else v


def load_ug() -> pd.DataFrame:
    """Consulta oficial 'Execução TED por UG' (4 blocos, um por ano)."""
    txt = open(
        f"{REPO}Execução TED por UG - 2023_24_25 e 26.csv", encoding="latin1"
    ).read()
    out, ano = [], None
    for line in txt.splitlines():
        m = re.match(r"Ano Lançamento: (\d{4})", line)
        if m:
            ano = int(m.group(1))
            continue
        r = next(csv.reader([line], delimiter="\t")) if line.startswith('"') else None
        if not r or not re.fullmatch(r"\d{5}", r[0]) or r[4] == "Total":
            continue
        out.append(
            dict(
                ano=ano,
                orgao=r[0],
                orgao_nome=r[1],
                ug=r[2],
                ug_nome=r[3],
                acao=r[4],
                po=r[6],
                po_nome=r[7],
                ptres=r[8],
                grupo=r[9],
                fonte=r[10],
                destaque=num(r[11]),
                disponivel=num(r[12]),
                empenhado=num(r[13]),
                liquidado=num(r[14]),
                pago=num(r[15]),
            )
        )
    return pd.DataFrame(out)


def _ppa(arquivos: list[tuple[int, str]]) -> pd.DataFrame:
    out = []
    for ano, arq in arquivos:
        rows = list(csv.reader(io.StringIO(open(REPO + arq, encoding="latin1").read())))
        hdr = next(r for r in rows if r and r[0] == "Programa Governo Código")
        for r in rows:
            if len(r) < 33 or not re.fullmatch(r"\d{4}", r[0] or ""):
                continue
            d: dict[str, Any] = dict(zip(hdr[:32], r[:32]))
            d["ano"] = ano
            for i in range(32, len(hdr)):
                d["m" + hdr[i]] = num(r[i]) if i < len(r) else 0.0
            out.append(d)
    df = pd.DataFrame(out).rename(
        columns={
            "NE CCor Número": "ne_ccor",
            "Ação Governo Código": "acao",
            "Plano Orçamentário Código PO": "po",
            "PTRES Código": "ptres",
            "Fonte Recursos Detalhada Código": "fonte",
            "Grupo Despesa Código Grupo": "grupo",
            "Resultado EOF Código": "rp",
            "UG Responsável Código": "ug_resp",
        }
    )
    df["ug"] = df.ne_ccor.str[:6]
    return df.fillna({c: 0.0 for c in df.columns if c.startswith("m")})


def load_ne_antigo() -> pd.DataFrame:
    """CSVs antigos (moeda origem, saldo >= 0,01): só dão o universo de UGs."""
    return _ppa([(y, f"{y}.csv") for y in (2023, 2024, 2025, 2026)])


def load_ne_reais() -> pd.DataFrame:
    """Relatório 'Notas de empenhos por programa PPA (EM REAIS)'."""
    return _ppa([(y, f"ppa_tesouro({y}).csv") for y in (2023, 2024, 2025, 2026)])


def ref(nome: str) -> pd.DataFrame:
    return pd.read_csv(DADOS + nome, dtype=str)


def tuplas(df: pd.DataFrame) -> list[Any]:
    """Linhas do DataFrame como namedtuples (tipadas como Any para o mypy)."""
    return list(df.itertuples())
