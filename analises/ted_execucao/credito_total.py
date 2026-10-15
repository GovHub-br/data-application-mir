"""Crédito por instrumento na célula (ano, órgão, PTRES, fonte).

Inclui os tedinhos: NC do MIR sem nº de transferência.
"""

import pandas as pd
from carga import load_ug, ref

ug = load_ug()
orgao_da_ug = ug.drop_duplicates("ug").set_index("ug").orgao.to_dict()
MIR = ("238", "810008", "240", "230002")  # UGs emitentes do MIR


def _v(s: pd.Series) -> pd.Series:
    neg = s.str.startswith("(") | s.str.startswith("-")
    x = (
        s.str.strip("()-")
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )
    return x.where(~neg, -x)


def credito() -> pd.DataFrame:
    ted = ref("nc.csv")
    ted["valor"] = ted.valor.astype(float) * ted.tipo.map(
        {"Recebido": 1, "Devolvido": -1, "Anulado": -1}
    )
    ted = ted.assign(
        ano=ted.ano.astype(int),
        instrumento=ted.num_transf,
        orgao_ug=ted.ug.map(orgao_da_ug),
    )

    r = pd.concat([ref("nc_raw1.csv"), ref("nc_raw2.csv")]).drop_duplicates()
    r["v"] = _v(r.valor.fillna("0"))
    r["ano"] = r.nc.str[11:15].astype(int)
    r["emit"] = r.nc.str[:6]
    tdn = r[
        (r.nc_transferencia == "-8")
        & r.emit.str.startswith(MIR)
        & (r.relatorio == "enviadas")
        & ~r.fav.str.startswith(MIR)
    ]
    tdn = tdn.assign(
        instrumento="tedinho " + tdn.nc, orgao_ug=tdn.fav.map(orgao_da_ug), valor=tdn.v
    )
    dev = r[
        (r.nc_transferencia == "-8")
        & (r.relatorio == "recebidas")
        & r.fav.str.startswith(MIR)
        & ~r.emit.str.startswith(MIR)
    ]
    dev = dev.assign(
        instrumento="(devolução sem TED)", orgao_ug=dev.emit.map(orgao_da_ug), valor=dev.v
    )
    cols = ["ano", "orgao_ug", "ptres", "fonte", "instrumento", "valor"]
    return pd.concat([ted[cols], tdn[cols], dev[cols]])


if __name__ == "__main__":
    c = credito()
    KC = ["ano", "orgao_ug", "ptres", "fonte"]
    ug["orgao_ug"] = ug.ug.map(orgao_da_ug)
    dest = ug.groupby(KC).destaque.sum()
    tot = c.groupby(KC).valor.sum()
    j = pd.concat([tot.rename("nc"), dest.rename("destaque")], axis=1).fillna(0)
    j["ok"] = (j.nc - j.destaque).abs() < 0.01
    print(
        "células em que NC (TED + tedinho) = destaque oficial:", j.ok.sum(), "de", len(j)
    )
    print(
        j[~j.ok]
        .assign(dif=j.nc - j.destaque)
        .sort_values("dif", key=abs, ascending=False)
        .head(15)
        .round(2)
    )
