"""Execução dos TEDs do MIR: a consulta 'Execução TED por UG' aberta por instrumento.

Base de NEs: ppa_tesouro(AAAA).csv (em R$, com anulações), recortada como a consulta
oficial (RP 2, sem as UGs/ações excluídas, só UGs fora do MIR) e com 2026 cortado em
30/09/2026 (posição da consulta oficial). Nessa base as células oficiais fecham 100%.

Camadas de identificação, em ordem (cada NE fica com a primeira que a resolver):
  1 cascata dbt       vínculo NE -> TED de siafi_dbt.empenhos_por_plano_acao (dump)
  2 regras            A1 nº TransfereGov no texto; A2 numeração MIR (gov.br);
                      D NC citada; B NE de referência (reforço); C mesmo processo;
                      E mesmo contrato
  3 similaridade      F texto da NE x objeto do plano do mesmo órgão
                      (score >= 0,3 e margem >= 0,1)
  -- vínculo cujo número não é TED do MIR (nem plano de ação, nem NC de crédito
     vinculada) é descartado --
  -- vínculo que contradiz o crédito da célula é descartado (só similaridade, ou
     quando o crédito é só de outros TEDs numerados) --
  4 crédito da UG     G1 todo o destaque da célula (ano, órgão, PTRES, fonte) veio
                      de um único instrumento (TED ou tedinho);
                      G2 empenho sem TED = saldo exato de crédito de um TED da célula
  5 tedinho/subdesc.  T NC do MIR citada no texto, com ou sem ano (tedinho = a NC);
                      S NC citada de outro órgão que tem um único TED com o MIR no
                      ano + PTRES (desempate pela fonte)
  6 não identificado

Tedinho = NC do MIR sem nº de transferência. Quando a página do gov.br lista a
descentralização ("Processo: 21290..."), o tedinho leva o processo no nome.
"""

import math
import re
import unicodedata
from collections import Counter
from typing import Callable, cast

import pandas as pd

from carga import K, SAIDA, load_ne_antigo, load_ne_reais, load_ug, ref
from credito_total import credito
from govbr_pagina import instrumentos_da_pagina

EXCL_UG = {"810008", "170607", "170605", "201057", "230003", "810005", "238012"}
EXCL_ACAO = {"2000", "216H", "4641"}
CORTE_2026 = "2026-09-30"

# ---------------------------------------------------------------- base
ug = load_ug()
orgao_da_ug = ug.drop_duplicates("ug").set_index("ug").orgao.to_dict()
ugs = set(ug.ug) | set(load_ne_antigo().ug)

n = load_ne_reais()
dt = pd.to_datetime(n["Emissão - Dia Data Completa"], format="%d/%m/%Y", errors="coerce")
f = n[
    (n.rp == "2")
    & ~n.ug.isin(EXCL_UG)
    & ~n.acao.str.upper().isin(EXCL_ACAO)
    & n.ug.isin(ugs)
    & ((n.ano < 2026) | (dt <= pd.Timestamp(CORTE_2026)) | dt.isna())
].copy()
f = f.rename(
    columns={
        "m29": "emp",
        "m31": "liq",
        "m34": "pag",
        "Doc - Observação Texto": "doc_observacao",
    }
)

oficial = ug.groupby(K)[["empenhado", "liquidado", "pago"]].sum()
chk = f.groupby(K)[["emp", "liq", "pag"]].sum().join(oficial, how="outer").fillna(0)
diverg = sum(
    ((chk[a] - chk[b]).abs() >= 0.01).sum()
    for a, b in [("emp", "empenhado"), ("liq", "liquidado"), ("pag", "pago")]
)
print(f"reconciliação NE x consulta oficial: {len(chk)} células, {diverg} divergências")

mapa = (
    ref("map_ted.csv")
    .dropna(subset=["num_transf"])
    .groupby("ne_ccor")
    .num_transf.agg(lambda s: s.mode()[0])
)
f["ted"] = f.ne_ccor.map(mapa)
f["camada"] = f.ted.map(lambda t: None if pd.isna(t) else "1 cascata dbt")

texto = (
    f.groupby("ne_ccor")
    .apply(
        lambda g: " | ".join(
            [
                str(g["NE CCor - Descrição Texto"].iloc[0]),
                str(g["NE - Informação Complementar Texto"].iloc[0]),
            ]
            + sorted(set(g.doc_observacao.dropna()))
        )
    )
    .str.upper()
)
descricao = f.groupby("ne_ccor")["NE CCor - Descrição Texto"].first()
processo = (
    f[f["NE - Núm. Processo Número"] != "-9"]
    .groupby("ne_ccor")["NE - Núm. Processo Número"]
    .first()
)

na_oficial = pd.Series(
    [tuple(r) in set(oficial.index) for r in f[K].itertuples(index=False)], index=f.index
)
alvo = sorted(
    set(
        f[
            na_oficial
            & f.ted.isna()
            & (f[["emp", "liq", "pag"]].abs() > 0.005).any(axis=1)
        ].ne_ccor
    )
)

# ---------------------------------------------------------------- referências
pa = ref("pa.csv").dropna(subset=["num_transf"])
pa["orgao"] = pa.ug_rec.map(orgao_da_ug)
# TED com NC de crédito vinculada também é TED do MIR (ex.: 698627, anterior ao cadastro)
_nc_ted = ref("nc.csv")
teds_mir = set(pa.num_transf) | set(_nc_ted.num_transf.dropna())
orgao_do_ted: dict[str, set[str]] = {
    str(t): set(o.dropna()) for t, o in pa.groupby("num_transf").orgao
}
for _t, _o in _nc_ted.assign(o=_nc_ted.ug.map(orgao_da_ug)).groupby("num_transf").o:
    orgao_do_ted.setdefault(_t, set()).update(_o.dropna())
plano_transf = pa.set_index("id_plano_acao").num_transf.to_dict()
gov = ref("govbr.csv").dropna(subset=["num_transf"])
gnum = gov.groupby("numero_ted").num_transf.agg(set).to_dict()
ncpa = ref("ncpa.csv").dropna(subset=["id_plano_acao"])
ncpa["suf"] = ncpa.nc.str[-12:]

nc = ref("nc.csv")
nc["ano"] = nc.ano.astype(int)
nc["valor"] = nc.valor.astype(float) * nc.tipo.map(
    {"Recebido": 1, "Devolvido": -1, "Anulado": -1}
)
nc["orgao"] = nc.ug.map(orgao_da_ug)
nc["orgao_ug"] = nc.orgao
nc_raw = pd.concat([ref("nc_raw1.csv"), ref("nc_raw2.csv")])
nc_raw["suf"] = nc_raw.nc.str[-12:]

vinc = (
    f.dropna(subset=["ted"]).groupby("ne_ccor").ted.agg(lambda s: s.mode()[0]).to_dict()
)
achado: dict[str, tuple[str, str]] = {}


def org(ne: str) -> str | None:
    return orgao_da_ug.get(ne[:6])


def ok_orgao(ne: str, t: str) -> bool:
    return org(ne) in orgao_do_ted.get(t, set())


def ted_de(ne: str) -> str | None:
    return vinc.get(ne) or (achado[ne][0] if ne in achado else None)


# ------------------------------------------------------- 2 regras determinísticas
for ne in alvo:  # A1
    toks = set(re.findall(r"\b([0-9]{6}|[0-9][A-Z]{3}[A-Z0-9]{2})\b", texto.get(ne, "")))
    c = {t for t in toks & teds_mir if ok_orgao(ne, t)}
    if len(c) == 1:
        achado[ne] = (c.pop(), "A1 nº TransfereGov no texto")

for ne in alvo:  # A2
    if ne in achado:
        continue
    c = set()
    for nn, a in re.findall(
        r"TED\s*(?:MIR|SEPAR/MIR|SEPAR|N[º°O]?\.?)?\s*(?:N[º°O]\.?\s*)?"
        r"([0-9]{1,2})\s*/\s*([0-9]{4}|[0-9]{2})\b",
        texto.get(ne, ""),
    ):
        c |= {
            t
            for t in gnum.get(f"{int(nn):02d}/{a if len(a) == 4 else '20' + a}", set())
            if ok_orgao(ne, t)
        }
    if len(c) == 1:
        achado[ne] = (c.pop(), "A2 numeração MIR (gov.br)")

for ne in alvo:  # D
    if ne in achado:
        continue
    c = set()
    for suf in re.findall(r"([0-9]{4}NC[0-9]{6})", texto.get(ne, "")):
        m = ncpa[
            (ncpa.suf == suf)
            & (
                (ncpa.favorecido_doc.map(orgao_da_ug) == org(ne))
                | (ncpa.ug_emitente.map(orgao_da_ug) == org(ne))
            )
        ]
        c |= {plano_transf[p] for p in m.id_plano_acao if p in plano_transf}
    if len(c) == 1:
        achado[ne] = (c.pop(), "D NC citada no texto")


def propaga(chaves_fn: Callable[[str], list[tuple]], rotulo: str) -> None:
    grupos: dict[tuple, set[str]] = {}
    for ne in texto.index:
        for k in chaves_fn(ne):
            grupos.setdefault(k, set()).add(ne)
    mudou = True
    while mudou:
        mudou = False
        for ne in alvo:
            if ne in achado:
                continue
            c: set[str] = set()
            for k in chaves_fn(ne):
                c |= {t for x in grupos[k] if x != ne and (t := ted_de(x)) is not None}
            c = {t for t in c if ok_orgao(ne, t)}
            if len(c) == 1:
                achado[ne] = (c.pop(), rotulo)
                mudou = True


por_suf = {(ne[:6], ne[-12:]): ne for ne in texto.index}
pares: dict[str, set[str]] = {}
for ne in texto.index:
    for s in re.findall(r"([0-9]{4}NE[0-9]{6})", texto[ne]):
        o = por_suf.get((ne[:6], s))
        if o and o != ne:
            pares.setdefault(ne, set()).add(o)
            pares.setdefault(o, set()).add(ne)
propaga(
    lambda ne: [tuple(sorted((ne, x))) for x in pares.get(ne, ())],
    "B NE de referência (reforço)",
)


def processos(ne: str) -> list[tuple]:
    ps = {
        re.sub(r"\D", "", p)
        for p in re.findall(
            r"([0-9]{5}[.\s]?[0-9]{6}[/.\s]?[0-9]{4}[-.\s]?[0-9]{2})", texto.get(ne, "")
        )
    }
    p = re.sub(r"\D", "", str(processo.get(ne, "")))
    if len(p) >= 15:
        ps.add(p[-17:])
    return [("proc", org(ne), p[-17:]) for p in ps if len(p) >= 15]


propaga(processos, "C mesmo processo")
propaga(
    lambda ne: [
        ("ctr", org(ne), re.sub(r"\s", "", a))
        for a in re.findall(
            r"CONTRATO\s+([A-Z./-]*\s*[0-9]{1,4}/[0-9]{4})", texto.get(ne, "")
        )
    ],
    "E mesmo contrato",
)

# ---------------------------------------------------------------- 3 similaridade
STOP = set(
    """A O E DE DA DO DAS DOS EM NO NA NOS NAS PARA POR COM AO AOS AS OS UM UMA SE QUE
OU À PELA PELO PELAS PELOS SOBRE ENTRE SEU SUA SEUS SUAS ESTA ESTE NAO
EMPENHO EMPENHAR ATENDER DESPESA DESPESAS CONTRATACAO FUNDACAO APOIO PROJETO PROCESSO
EXECUCAO REFERENTE CONFORME CONTRATO SERVICOS SERVICO PRESTACAO GESTAO ADMINISTRATIVA
FINANCEIRA TED MIR NE NC UFF UFMA UFRB IFG IFMA DISPENSA SOLICITANTE NOTA FAVOR""".split()
)


def tok(s: object) -> list[str]:
    s = (
        unicodedata.normalize("NFKD", str(s or ""))
        .encode("ascii", "ignore")
        .decode()
        .upper()
    )
    return [w for w in re.findall(r"[A-Z]{3,}", s) if w not in STOP]


planos = pa.drop_duplicates("num_transf").copy()
planos["tok"] = planos.objeto.map(tok)
ne_tok = {ne: tok(descricao.get(ne, "")) for ne in texto.index}
df_: Counter[str] = Counter()
for t in list(planos.tok) + list(ne_tok.values()):
    df_.update(set(t))
N = len(planos) + len(ne_tok)
idf = {w: math.log(N / (1 + c)) for w, c in df_.items()}


def vec(t: list[str]) -> dict[str, float]:
    v = {w: c * idf.get(w, 0) for w, c in Counter(t).items()}
    nrm = math.sqrt(sum(x * x for x in v.values())) or 1
    return {w: x / nrm for w, x in v.items()}


pvec = dict(zip(planos.num_transf, planos.tok.map(vec)))
porg = planos.groupby("orgao").num_transf.agg(list).to_dict()


def melhor(ne: str) -> tuple[str | None, float, float]:
    v = vec(ne_tok.get(ne, []))
    c = sorted(
        (
            (sum(x * pvec[t].get(w, 0) for w, x in v.items()), t)
            for t in porg.get(org(ne), [])
        ),
        reverse=True,
    )
    if not c:
        return None, 0, 0
    return c[0][1], c[0][0], c[0][0] - (c[1][0] if len(c) > 1 else 0)


for ne in alvo:
    if ne in achado:
        continue
    t, s, mg = melhor(ne)
    if t and s >= 0.3 and mg >= 0.1:
        achado[ne] = (t, "F similaridade com objeto do plano")

sem = f.ted.isna()
f.loc[sem, "camada"] = f.loc[sem, "ne_ccor"].map(lambda x: achado.get(x, (None, None))[1])
f.loc[sem, "ted"] = f.loc[sem, "ne_ccor"].map(lambda x: achado.get(x, (None, None))[0])

# vínculo com número que não é TED do MIR: descarta
falso = f.ted.notna() & ~f.ted.isin(teds_mir)
print(
    "vínculos descartados (número não é TED do MIR): "
    f"{f[falso & na_oficial].ne_ccor.nunique()} NEs, "
    f"R$ {f[falso & na_oficial].emp.sum():,.2f}"
)
f.loc[falso, ["ted", "camada"]] = None

# ---------------------------------------------------------------- 4 crédito da UG
f = f[na_oficial].copy()
f["orgao_ug"] = f.ug.map(orgao_da_ug)
ug["orgao_ug"] = ug.ug.map(orgao_da_ug)
KC = ["ano", "orgao_ug", "ptres", "fonte"]
_c = credito()  # NCs de TED + tedinhos (NC do MIR sem nº de transferência)
cred_cel = _c.groupby(KC).valor.sum()  # total da célula, inclusive devoluções sem TED
cred = (
    _c[_c.instrumento != "(devolução sem TED)"].groupby(KC + ["instrumento"]).valor.sum()
)
cred = cred[cred > 0.005]
dest = ug.groupby(KC).destaque.sum()

# checagem: vínculo por texto/similaridade x crédito de células totalmente explicadas
cobertas = {k for k in cred_cel.index if abs(cred_cel[k] - dest.get(k, 0)) < 0.01}
f["k"] = list(zip(*[f[c] for c in KC]))
txt_lig = f.camada.notna() & f.camada.str[0].isin(list("1ABCDEF"))
conf = f[txt_lig & f.k.isin(cobertas)].copy()
conf["no_credito"] = [
    t in set(cred.loc[k].index) if k in cred.index.droplevel("instrumento") else False
    for t, k in zip(conf.ted, conf.k)
]
conf = conf[~conf.no_credito]
# NC sem nº de transferência pode ser crédito do próprio TED citado no texto (ex.: INCRA,
# TED 698627 com a NC 810008 2023NC000015 sem nº): aí o texto vale. Só derrubam o vínculo
# a similaridade ou o crédito exclusivo de outros TEDs numerados.
tem_tedinho = {
    k
    for k in cobertas
    if k in cred.index.droplevel("instrumento")
    and any(str(i).startswith("tedinho") for i in cred.loc[k].index)
}
conf = conf[conf.camada.str.startswith("F") | ~conf.k.isin(tem_tedinho)]
print("\nvínculos por texto/similaridade em TED que NÃO mandou crédito para a célula:")
print(
    conf.groupby("camada")
    .agg(nes=("ne_ccor", "nunique"), emp=("emp", "sum"))
    .round(2)
    .to_string()
)
conf.to_pickle(SAIDA + "conflitos_credito.pkl")
# o crédito prevalece: a NE volta para as regras do crédito
f.loc[conf.index, ["ted", "camada"]] = None


def exclusivo(k: tuple) -> str | None:
    if (
        k in cred_cel.index
        and len(cred.loc[k]) == 1
        and abs(cred_cel[k] - dest.get(k, 0)) < 0.01
    ):
        return str(cred.loc[k].index[0])
    return None


sem = f.ted.isna()
g1 = f.loc[sem, "k"].map(exclusivo)
f.loc[g1.dropna().index, "ted"] = g1.dropna()
f.loc[g1.dropna().index, "camada"] = "G1 crédito exclusivo"

ident = f[f.ted.notna()].groupby(KC + ["ted"]).emp.sum()
for kk, v in f[f.ted.isna()].groupby("k").emp.sum().items():
    k = cast(tuple, kk)
    if abs(v) < 0.005 or k not in cred_cel.index or len(cred.loc[k]) < 2:
        continue
    idk = ident.loc[k] if k in ident.index.droplevel("ted") else pd.Series(dtype=float)
    hit = [t for t, c in cred.loc[k].items() if abs(c - idk.get(t, 0.0) - v) < 0.01]
    if len(hit) == 1:
        idx = f[(f.k == k) & f.ted.isna()].index
        f.loc[idx, "ted"] = hit[0]
        f.loc[idx, "camada"] = "G2 saldo exato de um TED"

# G3 repasse por outro órgão: a célula não recebeu NC do MIR, mas um instrumento do MIR
# do mesmo ano/PTRES/fonte foi para outro órgão, que repassou (crédito recebido menos
# o destaque que executou) exatamente o destaque da célula. Ex.: TED 949807, MIR ->
# MinC (UG 540026, sem execução) -> UNIFESP, R$ 400 mil.
_rep = cred.reset_index()
_rep["repassado"] = _rep.valor - [
    dest.get((a, o, p, fo), 0.0)
    for a, o, p, fo in zip(_rep.ano, _rep.orgao_ug, _rep.ptres, _rep.fonte)
]
_rep = _rep[_rep.repassado > 0.005]
_com_credito = set(cred.index.droplevel("instrumento"))


def repasse_com_origem(k: tuple) -> tuple[str, tuple] | None:
    """Instrumento repassado à célula k e a célula de onde saiu o repasse."""
    if k in _com_credito or abs(dest.get(k, 0.0)) < 0.005:
        return None
    a, o, p, fo = k
    c = _rep[
        (_rep.ano == a) & (_rep.ptres == p) & (_rep.fonte == fo) & (_rep.orgao_ug != o)
    ]
    c = c[(c.repassado - dest[k]).abs() < 0.01]
    if c.instrumento.nunique() != 1 or len(c) != 1:
        return None
    z = c.iloc[0]
    return str(z.instrumento), (z.ano, z.orgao_ug, z.ptres, z.fonte)


def repasse(k: tuple) -> str | None:
    r = repasse_com_origem(k)
    return r[0] if r else None


_val = f[f.ted.notna() & ~f.k.isin(_com_credito)].drop_duplicates("ne_ccor")
_ok = [(t, r) for t, r in zip(_val.ted, _val.k.map(repasse)) if r is not None]
print(
    f"G3 validação (NEs já ligadas): {sum(t == r for t, r in _ok)}/{len(_ok)} concordam"
)
sem = f.ted.isna()
g3 = f.loc[sem, "k"].map(repasse)
f.loc[g3.dropna().index, "ted"] = g3.dropna()
f.loc[g3.dropna().index, "camada"] = "G3 repasse por outro órgão"

# G1b crédito exclusivo descontado o repasse: a célula recebeu um único instrumento,
# que repassou parte a outro órgão (repasse já atribuído pela G3); o que sobra é
# exatamente o destaque oficial. Ex.: Palmares 2025, TED 966942: R$ 408 mil
# recebidos, R$ 265 mil repassados à UnB, R$ 143 mil executados.
repassado: dict[tuple, float] = {}
for k in set(f.loc[g3.dropna().index, "k"]):
    r = repasse_com_origem(k)
    if r:
        repassado[(r[1], r[0])] = repassado.get((r[1], r[0]), 0.0) + dest[k]


def exclusivo_menos_repasse(k: tuple) -> str | None:
    if k not in _com_credito or len(cred.loc[k]) != 1:
        return None
    t = str(cred.loc[k].index[0])
    rep = repassado.get((k, t), 0.0)
    if rep > 0.005 and abs(cred_cel[k] - rep - dest.get(k, 0.0)) < 0.01:
        return t
    return None


sem = f.ted.isna()
g1b = f.loc[sem, "k"].map(exclusivo_menos_repasse)
f.loc[g1b.dropna().index, "ted"] = g1b.dropna()
f.loc[g1b.dropna().index, "camada"] = "G1b crédito exclusivo descontado o repasse"


# G4 saldo único: célula com 2+ instrumentos, crédito NC cobrindo o destaque oficial
# (nada de origem desconhecida), e só um instrumento com saldo depois do que as NEs
# identificadas consumiram. O empenho sem TED só pode ser desse instrumento.
def saldo_unico(k: tuple, sem_ted: float, ident_k: pd.Series) -> str | None:
    if k not in _com_credito or len(cred.loc[k]) < 2:
        return None
    if cred_cel.get(k, 0.0) < dest.get(k, 0.0) - 0.01:
        return None
    saldo = {t: v - ident_k.get(t, 0.0) for t, v in cred.loc[k].items()}
    com_saldo = [t for t, s in saldo.items() if s > 0.01]
    if len(com_saldo) == 1 and saldo[com_saldo[0]] >= sem_ted - 0.01:
        return str(com_saldo[0])
    return None


def ident_da_celula(df: pd.DataFrame, k: tuple) -> pd.Series:
    x = df[(df.k == k) & df.ted.notna()]
    return x.groupby("ted").emp.sum()


# validação leave-one-out: esconde cada NE ligada por texto numa célula de 2+
# instrumentos e vê se o saldo único aponta o mesmo TED
_acertos = _testes = 0
for ne, k, t in (
    f[f.ted.notna() & f.camada.str[0].isin(list("1ABCDE"))]
    .drop_duplicates("ne_ccor")[["ne_ccor", "k", "ted"]]
    .itertuples(index=False)
):
    if k not in _com_credito or len(cred.loc[k]) < 2:
        continue
    sem_ne = f[f.ne_ccor != ne]
    v = f[(f.ne_ccor == ne) & (f.k == k)].emp.sum()
    p = saldo_unico(k, v, ident_da_celula(sem_ne, k))
    if p is not None:
        _testes += 1
        _acertos += p == t
print(f"G4 validação leave-one-out: {_acertos}/{_testes} concordam")


def aplica_saldo_unico() -> None:
    for kk, v in f[f.ted.isna()].groupby("k").emp.sum().items():
        k = cast(tuple, kk)
        if abs(v) < 0.005:
            continue
        p = saldo_unico(k, v, ident_da_celula(f, k))
        if p is not None:
            idx = f[(f.k == k) & f.ted.isna()].index
            f.loc[idx, "ted"] = p
            f.loc[idx, "camada"] = "G4 saldo único na célula"


aplica_saldo_unico()

# ---------------------------------------------- 5 tedinho / subdescentralização
# NCs do MIR para fora do MIR, com o instrumento (TED ou tedinho = a própria NC)
nc_mir = nc_raw[
    nc_raw.nc.str[:6].isin(["238012", "810008"]) & (nc_raw.relatorio == "enviadas")
].copy()
nc_mir["instrumento"] = nc_mir.nc_transferencia.where(
    nc_mir.nc_transferencia != "-8", "tedinho " + nc_mir.nc
)
nc_mir["ano_nc"] = nc_mir.nc.str[11:15]
nc_mir["seq"] = nc_mir.nc.str[-6:]
for ne in sorted(set(f[f.ted.isna()].ne_ccor)):
    t = texto.get(ne, "")
    linha = f[f.ne_ccor == ne].iloc[0]
    # NC citada com ano ("2025NC000307") ou sem ("NC000307 / 233518": vale o ano da NE)
    citadas = {(a, s) for a, s in re.findall(r"([0-9]{4})NC([0-9]{6})", t)}
    citadas |= {
        (str(linha.ano), s) for s in re.findall(r"(?<![0-9])NC\s?([0-9]{6})\b", t)
    }
    m = nc_mir[
        nc_mir[["ano_nc", "seq"]].apply(tuple, axis=1).isin(citadas)
        & ((nc_mir.fav.map(orgao_da_ug) == org(ne)) | (nc_mir.fav == ne[:6]))
        & (nc_mir.ptres == linha.ptres)
    ]
    inst = {i for i in set(m.instrumento) if i.startswith("tedinho") or i in teds_mir}
    if len(inst) == 1:
        i = inst.pop()
        achado[ne] = (
            i,
            (
                "T tedinho pela NC citada"
                if i.startswith("tedinho")
                else "T NC do MIR citada (TED)"
            ),
        )
        continue
    for e in re.findall(r"[0-9]{4}NC[0-9]{6}\s*\(([0-9]{6})/", t):
        if orgao_da_ug.get(e) is None or orgao_da_ug.get(e) == org(ne):
            continue
        cand = nc[(nc.ug == e) & (nc.ano == linha.ano) & (nc.ptres == linha.ptres)]
        c = set(cand.num_transf)
        if len(c) > 1:  # vários TEDs do intermediário no PTRES: desempata pela fonte
            c = set(cand[cand.fonte == linha.fonte].num_transf)
        if len(c) == 1:
            achado[ne] = (c.pop(), f"S subdescentralização via {e}")
        break
camada5 = {ne: v for ne, v in achado.items() if v[1][0] in "TS"}
sem = f.ted.isna()
f.loc[sem, "camada"] = f.loc[sem, "ne_ccor"].map(
    lambda x: camada5.get(x, (None, None))[1]
)
f.loc[sem, "ted"] = f.loc[sem, "ne_ccor"].map(lambda x: camada5.get(x, (None, None))[0])
# segunda passada do saldo único: a camada 5 identifica NEs que consomem saldo
aplica_saldo_unico()

f["camada"] = f.camada.fillna("6 não identificado")
GRUPO = {
    "1": "1 cascata dbt",
    "A": "2 regras determinísticas",
    "B": "2 regras determinísticas",
    "C": "2 regras determinísticas",
    "D": "2 regras determinísticas",
    "E": "2 regras determinísticas",
    "F": "3 similaridade",
    "G": "4 crédito da UG",
    "T": "5 tedinho / subdescentralização",
    "S": "5 tedinho / subdescentralização",
    "6": "6 não identificado",
}
f["grupo_camada"] = f.camada.str[0].map(GRUPO)
# tedinho listado na página do gov.br: o nome passa a ser o processo (ou o nº do TED
# sem Transferegov); NCs do mesmo processo viram um instrumento só
_pag = instrumentos_da_pagina()
rotulo = dict(zip(_pag.instrumento, _pag.rotulo))
f["ted"] = f.ted.map(lambda t: rotulo.get(t, t) if str(t).startswith("tedinho") else t)
f["tipo_instrumento"] = f.ted.map(
    lambda t: (
        None if pd.isna(t) else ("Tedinho" if str(t).startswith("tedinho") else "TED")
    )
)
f.drop(columns=["k"]).to_pickle(SAIDA + "base.pkl")

# ---------------------------------------------------------------- resumo e saídas
for metr, col in [("empenhado", "emp"), ("liquidado", "liq"), ("pago", "pag")]:
    x = f.pivot_table(
        index="ano", columns="grupo_camada", values=col, aggfunc="sum"
    ).fillna(0)
    x["total"] = x.sum(axis=1)
    x["oficial"] = ug.groupby("ano")[metr].sum()
    x.loc["total"] = x.sum()
    print(f"\n== {metr} (R$ mi)")
    print((x / 1e6).round(2).to_string())
    print(
        (x.drop(columns=["oficial", "total"]).div(x.total, axis=0) * 100)
        .round(1)
        .to_string()
    )
print("\npor regra (empenhado, R$ mi):")
print((f.groupby("camada").emp.sum() / 1e6).round(2).to_string())

pai = pa.drop_duplicates("num_transf").set_index("num_transf")
e = f.assign(ted=f.ted.fillna("(não identificado)"))
v = (
    e.groupby(["ano", "ted"])[["emp", "liq", "pag"]]
    .sum()
    .join(
        e.pivot_table(
            index=["ano", "ted"], columns="grupo_camada", values="emp", aggfunc="sum"
        )
        .fillna(0)
        .add_prefix("emp_")
    )
)
v = (
    v.round(2)
    .reset_index()
    .rename(
        columns={
            "emp": "empenhado",
            "liq": "liquidado",
            "pag": "pago",
            "ted": "instrumento",
        }
    )
)
v.insert(
    2,
    "tipo_instrumento",
    v.instrumento.map(
        lambda t: (
            "Tedinho" if t.startswith("tedinho") else ("TED" if t[0] != "(" else None)
        )
    ),
)
v["parceiro"] = v.instrumento.map(pai.sigla)
v["objeto"] = v.instrumento.map(pai.objeto.str.replace(r"\s+", " ", regex=True).str[:200])
v.to_csv(
    SAIDA + "execucao_por_ted.csv",
    index=False,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
)
f.drop(columns=["k"]).to_csv(
    SAIDA + "execucao_por_ne.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig"
)

u = f[f.camada.str.startswith("6")]
nu = (
    u.groupby(["ano", "ug", "ne_ccor", "acao", "po", "ptres", "fonte", "grupo"])
    .agg(
        empenhado=("emp", "sum"),
        liquidado=("liq", "sum"),
        pago=("pag", "sum"),
        favorecido=("NE CCor - Favorecido Nome", "first"),
        processo=("NE - Núm. Processo Número", "max"),
        descricao=("NE CCor - Descrição Texto", "first"),
    )
    .reset_index()
)
nu = nu[(nu[["empenhado", "liquidado", "pago"]].abs() > 0.005).any(axis=1)]
nu.insert(2, "ug_nome", nu.ug.map(ug.drop_duplicates("ug").set_index("ug").ug_nome))
nu.sort_values("empenhado", ascending=False).round(2).to_csv(
    SAIDA + "ne_nao_identificadas.csv",
    index=False,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
)
print(
    "\ninstrumentos com execução:",
    v[v.tipo_instrumento.notna()]
    .groupby("tipo_instrumento")
    .instrumento.nunique()
    .to_dict(),
    "| NEs não identificadas:",
    len(nu),
)
