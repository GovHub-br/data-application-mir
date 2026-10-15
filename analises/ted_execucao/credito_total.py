"""Crédito por instrumento na célula (ano, órgão, PTRES, fonte).

Inclui os tedinhos: NC do MIR sem nº de transferência.
"""

import pandas as pd
from carga import load_ug, ref, tuplas

ug = load_ug()
orgao_da_ug = ug.drop_duplicates("ug").set_index("ug").orgao.to_dict()
MIR = ("238", "810008", "240", "230002")  # UGs emitentes do MIR


def orgao(ugs: pd.Series) -> pd.Series:
    """Órgão da UG pela consulta oficial; UG fora dela (ex.: MinC, que só repassou)
    fica com a própria UG, para não sumir nos agrupamentos."""
    return ugs.map(orgao_da_ug).fillna("UG " + ugs)


def valor_com_sinal(s: pd.Series) -> pd.Series:
    """Valor do Tesouro Gerencial (1.234,56 / -1.234,56 / (1.234,56)) com sinal."""
    neg = s.str.startswith("(") | s.str.startswith("-")
    x = (
        s.str.strip("()-")
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )
    return x.where(~neg, -x)


def _itens(df: pd.DataFrame, contraparte: str) -> pd.DataFrame:
    """Uma linha por NC: contraparte (UG do outro lado), ano, total e itens (|valor|)."""
    return (
        df.groupby("nc")
        .agg(
            ug=(contraparte, "first"),
            ano=("ano", "first"),
            total=("v", "sum"),
            itens=("v", lambda s: tuple(sorted(round(abs(x), 2) for x in s))),
        )
        .reset_index()
    )


def casar_negativas(tdn: pd.DataFrame, dev: pd.DataFrame) -> dict[str, str]:
    """NC sem nº de transferência -> instrumento (NC que ela é, ou que ela abate).

    Anulação (NC do MIR negativa) ou devolução (NC do recebedor para o MIR) abate a NC
    positiva de itens idênticos ou, se não houver, a de mesmo valor total, para a mesma
    UG e o mesmo ano; cada NC positiva é cancelada uma vez só. Se o valor total empata
    entre NCs positivas, elas são um cancela-e-relança da mesma descentralização e
    viram um instrumento só ("NC_A / NC_B")."""
    pos = _itens(tdn, "fav")
    neg = pd.concat([_itens(tdn, "fav"), _itens(dev, "emit")])
    pos = pos[pos.total > 0.005]
    neg = neg[neg.total < -0.005]
    mapa: dict[str, str] = {}
    abatidas: set[str] = set()
    for por_itens in (True, False):  # primeiro itens idênticos, depois valor total
        for n in tuplas(neg):
            if str(n.nc) in mapa:
                continue
            cand = pos[(pos.ug == n.ug) & (pos.ano == n.ano) & ~pos.nc.isin(abatidas)]
            if por_itens:
                hit = cand[cand.itens == n.itens]
            else:
                hit = cand[(cand.total + n.total).abs() < 0.01]
            if len(hit) == 1 or (not por_itens and 2 <= len(hit) <= 3):
                rotulo = " / ".join(sorted(hit.nc.astype(str)))
                mapa[str(n.nc)] = rotulo
                for p in hit.nc.astype(str):
                    mapa[p] = rotulo
                    abatidas.add(p)
    return mapa


def _ncs_sem_numero() -> tuple[pd.DataFrame, pd.DataFrame]:
    """NCs do MIR sem nº de transferência (enviadas) e devoluções sem nº ao MIR."""
    r = pd.concat([ref("nc_raw1.csv"), ref("nc_raw2.csv")])
    r["v"] = valor_com_sinal(r.valor.fillna("0"))
    r["ano"] = r.nc.str[11:15].astype(int)
    r["emit"] = r.nc.str[:6]
    tdn = r[
        (r.nc_transferencia == "-8")
        & r.emit.str.startswith(MIR)
        & (r.relatorio == "enviadas")
        & ~r.fav.str.startswith(MIR)
    ]
    dev = r[
        (r.nc_transferencia == "-8")
        & (r.relatorio == "recebidas")
        & r.fav.str.startswith(MIR)
        & ~r.emit.str.startswith(MIR)
    ]
    return tdn, dev


_MAPA: dict[str, str] | None = None


def instrumento_da_nc(nc: str) -> str:
    """Nome do instrumento de uma NC do MIR sem nº ("tedinho <NC>" ou o par fundido)."""
    global _MAPA
    if _MAPA is None:
        _MAPA = casar_negativas(*_ncs_sem_numero())
    return "tedinho " + _MAPA.get(nc, nc)


def credito() -> pd.DataFrame:
    ted = ref("nc.csv")
    ted["valor"] = ted.valor.astype(float) * ted.tipo.map(
        {"Recebido": 1, "Devolvido": -1, "Anulado": -1}
    )
    ted = ted.assign(
        ano=ted.ano.astype(int),
        instrumento=ted.num_transf,
        orgao_ug=orgao(ted.ug),
    )
    tdn, dev = _ncs_sem_numero()
    # anulação/devolução abate a NC que ela cancela (cancela e relança é comum)
    tdn = tdn.assign(
        instrumento=tdn.nc.map(instrumento_da_nc), orgao_ug=orgao(tdn.fav), valor=tdn.v
    )
    abatida = dev.nc.map(lambda n: instrumento_da_nc(n) != "tedinho " + n)
    dev = dev.assign(
        instrumento=dev.nc.map(instrumento_da_nc).where(abatida, "(devolução sem TED)"),
        orgao_ug=orgao(dev.emit),
        valor=dev.v,
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
