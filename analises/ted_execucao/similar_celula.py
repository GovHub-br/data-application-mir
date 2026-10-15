"""Similaridade NE x objeto do instrumento (página gov.br + TransfereGov).

Restrita aos instrumentos que mandaram crédito para a célula (ano, órgão, PTRES,
fonte) da NE. Calibra nas NEs já identificadas por evidência e lista os candidatos
para as não identificadas.
"""

import math
import re
import unicodedata
from collections import Counter

import pandas as pd

from carga import SAIDA, ref, tuplas
from credito_total import credito
from govbr_pagina import instrumentos_da_pagina

KC = ["ano", "orgao_ug", "ptres", "fonte"]

# ------------------------------------------------ instrumentos e seus objetos
cred = credito()
cred = cred[cred.instrumento != "(devolução sem TED)"]
pos = cred.groupby(KC + ["instrumento"]).valor.sum()
pos = pos[pos > 0.005]
cand_celula = pos.reset_index().groupby(KC).instrumento.agg(list).to_dict()

pa = ref("pa.csv").dropna(subset=["num_transf"]).drop_duplicates("num_transf")

obj: dict[str, list[str]] = {}  # instrumento -> textos de objeto
for x in tuplas(instrumentos_da_pagina()):
    obj.setdefault(x.instrumento, []).append(str(x.objeto))
for p in tuplas(pa):
    obj.setdefault(p.num_transf, []).append(str(p.objeto))

STOP = set(
    """A O E DE DA DO DAS DOS EM NO NA NOS NAS PARA POR COM AO AOS AS OS UM UMA SE QUE
OU PELA PELO PELAS PELOS SOBRE ENTRE SEU SUA SEUS SUAS ESTA ESTE NAO EMPENHO EMPENHAR
ATENDER DESPESA DESPESAS CONTRATACAO FUNDACAO APOIO PROJETO PROCESSO EXECUCAO
REFERENTE CONFORME CONTRATO SERVICOS SERVICO PRESTACAO GESTAO ADMINISTRATIVA
FINANCEIRA TED MIR DISPENSA SOLICITANTE NOTA FAVOR PAGAMENTO VALOR TOTAL""".split()
)


def tok(s: object) -> list[str]:
    s = (
        unicodedata.normalize("NFKD", str(s or ""))
        .encode("ascii", "ignore")
        .decode()
        .upper()
    )
    return [w for w in re.findall(r"[A-Z]{4,}", s) if w not in STOP]


b = pd.read_pickle(SAIDA + "base.pkl")
ne_txt = (
    b.groupby("ne_ccor")
    .apply(
        lambda g: " ".join(
            [str(g["NE CCor - Descrição Texto"].iloc[0])]
            + sorted(set(g.doc_observacao.dropna()))
        )
    )
    .to_dict()
)
docs = {f"I:{t}": tok(" ".join(v)) for t, v in obj.items()}
docs.update({f"N:{n}": tok(v) for n, v in ne_txt.items()})
df_: Counter[str] = Counter()
for t in docs.values():
    df_.update(set(t))
idf = {w: math.log(len(docs) / (1 + c)) for w, c in df_.items()}


def vec(t: list[str]) -> dict[str, float]:
    v = {w: c * idf[w] for w, c in Counter(t).items()}
    n = math.sqrt(sum(x * x for x in v.values())) or 1
    return {w: x / n for w, x in v.items()}


V = {k: vec(t) for k, t in docs.items()}


def ranking(ne: str, cands: list[str]) -> list[tuple[float, str]]:
    v = V.get(f"N:{ne}", {})
    out = [
        (sum(x * V.get(f"I:{t}", {}).get(w, 0) for w, x in v.items()), t) for t in cands
    ]
    return sorted(out, reverse=True)


def prever(ne: str, k: tuple) -> tuple[str | None, float, float, int]:
    cands = cand_celula.get(k, [])
    if len(cands) < 2:
        return None, 0, 0, len(cands)
    rk = ranking(ne, cands)
    return rk[0][1], rk[0][0], rk[0][0] - rk[1][0], len(cands)


if __name__ == "__main__":
    b["k"] = list(zip(*[b[c] for c in KC]))
    sem_obj = [t for ks in cand_celula.values() for t in ks if t not in obj]
    com_credito = {t for ks in cand_celula.values() for t in ks}
    print(
        f"instrumentos com crédito: {len(com_credito)}, "
        f"sem objeto conhecido: {len(set(sem_obj))}"
    )

    # calibração: NEs com instrumento por evidência, em células com 2+ instrumentos
    det = b[b.camada.str[0].isin(list("1ABCDET")) & b.ted.notna()].drop_duplicates(
        "ne_ccor"
    )
    linhas = []
    for z in tuplas(det):
        pred, s, m, n = prever(z.ne_ccor, z.k)
        if pred is not None and z.ted in cand_celula.get(z.k, []):
            linhas.append((z.ne_ccor, z.ted, pred, s, m))
    cal = pd.DataFrame(linhas, columns=["ne", "verdade", "pred", "score", "margem"])
    cal["ok"] = cal.pred == cal.verdade
    print("\ncalibração (NEs com instrumento conhecido em células com 2+ instrumentos):")
    for s_min, m_min in [
        (0, 0),
        (0.1, 0.05),
        (0.2, 0.05),
        (0.2, 0.1),
        (0.3, 0.1),
        (0.3, 0.15),
    ]:
        x = cal[(cal.score >= s_min) & (cal.margem >= m_min)]
        print(
            f"  score>={s_min} margem>={m_min}: n={len(x):4d}  "
            f"precisão={x.ok.mean():.3f}  cobertura={len(x) / len(cal):.2f}"
        )

    # aplicação às NEs não identificadas
    u = b[b.camada.str.startswith("6")]
    g = u.groupby(["ne_ccor", "k", "ug"]).emp.sum().reset_index()
    aplic = []
    for z in tuplas(g):
        pred, s, m, n = prever(z.ne_ccor, z.k)
        aplic.append((z.ne_ccor, z.ug, z.k, z.emp, n, pred, round(s, 3), round(m, 3)))
    ap = pd.DataFrame(
        aplic, columns=["ne", "ug", "celula", "emp", "n_cand", "pred", "score", "margem"]
    )
    ap.to_pickle(SAIDA + "similar_celula.pkl")
    pd.set_option("display.width", 250)
    print("\nNEs não identificadas em células com 2+ instrumentos:")
    print(ap[ap.n_cand >= 2].sort_values("emp", ascending=False).to_string(index=False))
