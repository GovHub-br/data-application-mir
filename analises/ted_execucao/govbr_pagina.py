"""Entradas da página de transferências do MIR no gov.br, com o objeto.

Cobre os TEDs e as descentralizações sem TED (tedinhos).
"""

import glob
import html
import os
import re

import pandas as pd

from carga import DADOS

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
