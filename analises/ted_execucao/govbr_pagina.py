"""Entradas da página de transferências do MIR no gov.br, com o objeto.

Cobre os TEDs e as descentralizações sem TED (tedinhos).
"""

import glob
import html
import itertools
import os
import re
import unicodedata
from typing import Any, Callable

import pandas as pd

from carga import DADOS, load_ug, ref, tuplas
from credito_total import valor_com_sinal

PASTA = DADOS + "govbr_html/"
NUM_TRANSF = r"(?<![0-9A-Z])(\d{6}|\d[A-Z0-9]{5})(?![0-9A-Z])"
RE_TITULO = (
    r"^(Termo de Execu[cç][aã]o Descentralizada|TED\b"
    r"|Descentraliza[cç][aã]o de Cr[eé]dito\s*$)"
)
RE_PARCEIRO = (
    r"firmad[oa] entre o Minist[ée]rio da Igualdade Racial(?:\s*-\s*MIR)?\s+e\s+"
    r"(?:a|o|as|os)\s+(.+?)(?:\.\s|,\s*cujo|\s+Processo)"
)
RE_OBJETO = (
    r"Objeto\s*:?\s*[\"“”]?(.+?)[\"“”]?\s*,?\s*"
    r"(?:no valor|com valor|cujo valor|Valor|Vig[eê]ncia)"
)


def texto(h: str) -> str:
    i = h.find('id="content-core"')
    f = h.find('id="viewlet-below-content"', i)
    b = h[i : f if f > 0 else None]
    b = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", b, flags=re.S)
    b = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>|</tr>", "\n", b)
    b = html.unescape(re.sub(r"<[^>]+>", " ", b)).replace("\xa0", " ")
    b = re.sub(r"[ \t]+", " ", b)
    return re.sub(r"\n\s*\n+", "\n", b)


def entradas() -> pd.DataFrame:
    out = []
    for arq in sorted(glob.glob(PASTA + "*.html")):
        pagina = os.path.basename(arq)[:-5]
        linhas = [x.strip() for x in texto(open(arq).read()).splitlines() if x.strip()]
        titulo = None
        for ln in linhas:
            if (
                re.match(
                    RE_TITULO,
                    ln,
                    re.I,
                )
                and "firmado entre" not in ln
            ):
                titulo = ln
                continue
            if "firmado entre" not in ln or "Objeto" not in ln:
                continue
            if re.match(r"^\s*Termo Aditivo|^\s*Termo de Apostilamento", ln, re.I):
                continue
            cab = (titulo or "") + " " + ln[:200]
            num = re.search(r"n\s*[º°o.]?\s*(\d{1,3})\s*/\s*(\d{4})", cab, re.I)
            tg = re.search(r"Transfere\s*gov[^0-9\n]{0,15}?" + NUM_TRANSF, cab, re.I)
            parc = re.search(
                RE_PARCEIRO,
                ln,
                re.I,
            )
            proc = re.search(r"\b(\d{5}\.\d{6}/\d{4}-\d{2})\b", ln)
            obj = re.search(
                RE_OBJETO,
                ln,
                re.I,
            )
            val = re.search(r"R\$\s*([\d.]+,\d{2})", ln)
            descentr = bool(re.match(r"^Descentraliza", titulo or "", re.I)) and not num
            out.append(
                dict(
                    pagina=pagina,
                    tipo="Descentralização (sem TED)" if descentr else "TED",
                    numero_ted=f"{int(num.group(1)):02d}/{num.group(2)}" if num else None,
                    num_transf=tg.group(1) if tg else None,
                    parceiro=re.sub(r"\s+", " ", parc.group(1)).strip() if parc else None,
                    processo=proc.group(1) if proc else None,
                    objeto=obj.group(1).strip() if obj else None,
                    valor=(
                        float(val.group(1).replace(".", "").replace(",", "."))
                        if val
                        else None
                    ),
                    texto=ln,
                )
            )
            titulo = None
    return pd.DataFrame(out)


def _ncs_do_mir() -> pd.DataFrame:
    """NCs enviadas pelo MIR, com o valor total por NC e o nº de transferência."""
    r = pd.concat([ref("nc_raw1.csv"), ref("nc_raw2.csv")])
    r["v"] = valor_com_sinal(r.valor.fillna("0"))  # anulação entra negativa
    r = r[r.nc.str[:6].isin(["238012", "810008"]) & (r.relatorio == "enviadas")]
    return r.groupby(["nc", "nc_transferencia", "fav"]).v.sum().reset_index()


def _tedinhos_com_valor(
    nc_val: pd.DataFrame, valor: float, pagina: str, orgaos: set[str]
) -> list[str]:
    """NC sem nº de transferência do ano da página (ou do seguinte) com o valor exato,
    ou par de NCs cuja soma dá o valor. Se o órgão do parceiro é conhecido, só NCs
    para ele. Só vale se o casamento for único."""
    ano = int(pagina[:4])
    td = nc_val[
        (nc_val.nc_transferencia == "-8")
        & nc_val.nc.str[11:15].astype(int).isin([ano, ano + 1])
        & (nc_val.v > 0.005)
    ]
    if orgaos:
        td = td[td.orgao.isin(orgaos)]
    hit = list(td[(td.v - valor).abs() < 0.01].nc)
    if len(hit) == 1:
        return ["tedinho " + hit[0]]
    if hit:  # mesmo valor em mais de uma NC: ambíguo
        return []
    pares = [
        (a.nc, b.nc)
        for a, b in itertools.combinations(tuplas(td), 2)
        if abs(a.v + b.v - valor) < 0.01
    ]
    return ["tedinho " + n for n in pares[0]] if len(pares) == 1 else []


GENERICAS = set(
    """INSTITUTO FEDERAL UNIVERSIDADE FUNDACAO EDUCACAO CIENCIA TECNOLOGIA NACIONAL
ESCOLA ESTADO FEDERAIS CAMPUS REITORIA ADMINISTRACAO PUBLICA DESENVOLVIMENTO""".split()
)


def _norm(nome: object) -> str:
    s = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _palavras(nome: str) -> set[str]:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().upper()
    return {w for w in re.findall(r"[A-Z]{5,}", s) if w not in GENERICAS}


def _resolvedor_de_orgaos() -> Callable[[str], set[str]]:
    """Órgãos do parceiro: pela sigla no fim do nome (planos de ação) ou, para
    parceiro sem TED, pelas palavras distintivas do nome (ex.: "... de Pelotas")."""
    ug = load_ug()
    orgao_da_ug = ug.drop_duplicates("ug").set_index("ug").orgao.to_dict()
    palavras_orgao = {
        str(o): _palavras(
            " ".join(g.orgao_nome.unique()) + " " + " ".join(g.ug_nome.unique())
        )
        for o, g in ug.groupby("orgao")
    }
    pa = ref("pa.csv").dropna(subset=["sigla", "ug_rec"])
    orgaos_da_sigla: dict[str, set[str]] = {}
    for sg, u in zip(pa.sigla.str.upper(), pa.ug_rec):
        if u in orgao_da_ug:
            orgaos_da_sigla.setdefault(sg, set()).add(orgao_da_ug[u])

    def resolve(parceiro: str) -> set[str]:
        nome, _, sigla = parceiro.rpartition(" - ")
        orgaos = orgaos_da_sigla.get(sigla.strip().upper(), set())
        if not orgaos:
            pp = _palavras(nome or parceiro)
            orgaos = {o for o, pw in palavras_orgao.items() if pp and pp <= pw}
        return orgaos

    return resolve


def _alvos(
    x: Any, num_por_numero: dict, nc_val: pd.DataFrame, orgaos: set[str]
) -> list[str]:
    """Instrumento(s) de uma entrada da página."""
    if x.tipo != "TED":
        return _tedinhos_com_valor(nc_val, x.valor, x.pagina, orgaos) if x.valor else []
    t = x.num_transf or num_por_numero.get((x.numero_ted, _norm(x.parceiro)))
    if t:
        return [str(t)]
    if not x.valor:
        return []
    # TED sem nº do TransfereGov na página: nº do SIAFI cujo líquido (NCs menos
    # anulações) é o valor da página; senão, se a página dá o nº do TED, tedinho
    com_num = nc_val[nc_val.nc_transferencia != "-8"]
    liq = com_num[com_num.orgao.isin(orgaos)] if orgaos else com_num
    hit = [
        str(n)
        for n, v in liq.groupby("nc_transferencia").v.sum().items()
        if abs(v - x.valor) < 0.01
    ]
    if len(hit) == 1:
        return hit
    if not hit and x.numero_ted:
        return _tedinhos_com_valor(nc_val, x.valor, x.pagina, orgaos)
    return []


def instrumentos_da_pagina() -> pd.DataFrame:
    """Entradas da página ligadas ao instrumento: nº do TED no TransfereGov ou, para
    as descentralizações sem TED, 'tedinho <NC>' pela NC do MIR de mesmo valor."""
    # nº do TED (ex.: 01/2025) -> nº do TransfereGov, por parceiro: a página repete
    # números entre parceiros (01/2025 é da UFF e também do IFNMG)
    gov = ref("govbr.csv").dropna(subset=["num_transf"])
    num_por_numero = {
        (n, _norm(p)): t for n, p, t in zip(gov.numero_ted, gov.parceiro, gov.num_transf)
    }
    orgao_da_ug = load_ug().drop_duplicates("ug").set_index("ug").orgao.to_dict()
    nc_val = _ncs_do_mir()
    nc_val["orgao"] = nc_val.fav.map(orgao_da_ug)
    orgaos_do_parceiro = _resolvedor_de_orgaos()
    out = []
    for x in tuplas(entradas()):
        parceiro = str(x.parceiro or "")
        sigla = parceiro.rpartition(" - ")[2] or parceiro
        alvo = _alvos(x, num_por_numero, nc_val, orgaos_do_parceiro(parceiro))
        if x.processo and x.tipo != "TED":
            referencia = f"Processo {x.processo}"
        else:
            referencia = f"TED {x.numero_ted} (sem nº Transferegov)"
        for t in sorted(set(alvo)):
            out.append(
                dict(
                    instrumento=t,
                    rotulo=f"tedinho {referencia} ({sigla})",
                    pagina=x.pagina,
                    tipo=x.tipo,
                    numero_ted=x.numero_ted,
                    processo=x.processo,
                    parceiro=x.parceiro,
                    valor=x.valor,
                    objeto=x.objeto,
                )
            )
    return pd.DataFrame(out)


if __name__ == "__main__":
    e = entradas()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(e.groupby(["pagina", "tipo"]).size().unstack(fill_value=0))
    print(
        "sem objeto:",
        e.objeto.isna().sum(),
        "| sem valor:",
        e.valor.isna().sum(),
        "| sem parceiro:",
        e.parceiro.isna().sum(),
    )
    print(
        e[e.tipo != "TED"][["pagina", "parceiro", "processo", "valor", "objeto"]]
        .head(12)
        .to_string(index=False)
    )
    e.to_csv(
        PASTA + "../govbr_entradas.csv",
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig",
    )
