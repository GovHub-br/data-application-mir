"""Confere a camada de similaridade (F) contra as regras determinísticas.

Roda o pipeline sem a similaridade (SEM_SIMILARIDADE=1) e compara, NE a NE, o
instrumento que a similaridade deu com o que as regras determinísticas (crédito,
saldo, repasse) dão quando ela não existe:
  confirmado: mesmo instrumento;
  contém:     o determinístico só fecha num instrumento mesclado que inclui o da
              similaridade (ela é mais específica);
  diverge:    instrumento diferente;
  sem evidência: o determinístico não identifica.
"""

import os
import subprocess
import sys

import pandas as pd

from carga import SAIDA
from govbr_pagina import instrumentos_da_pagina

AQUI = os.path.dirname(os.path.abspath(__file__))


def roda(sem_similaridade: bool) -> None:
    env = dict(os.environ)
    env.pop("SEM_SIMILARIDADE", None)
    if sem_similaridade:
        env["SEM_SIMILARIDADE"] = "1"
    subprocess.run(
        [sys.executable, "-W", "ignore", "pipeline.py"],
        cwd=AQUI,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    roda(sem_similaridade=True)
    roda(sem_similaridade=False)  # por último, para as saídas ficarem completas
    com = pd.read_pickle(SAIDA + "base.pkl")
    sem = pd.read_pickle(SAIDA + "base_sem_similaridade.pkl")
    pag = instrumentos_da_pagina()
    pag = pag[pag.instrumento.str.startswith("tedinho")]
    rotulo = dict(zip(pag.instrumento, pag.rotulo))

    f = com[com.camada.str.startswith("F")].groupby(["ne_ccor", "ted"]).emp.sum()
    f = f.reset_index()
    det = sem.drop_duplicates("ne_ccor").set_index("ne_ccor")
    f["ted_deterministico"] = f.ne_ccor.map(
        det.ted.map(
            lambda t: (
                " + ".join(rotulo.get(p, p) for p in t.split(" + "))
                if isinstance(t, str)
                else t
            )
        )
    )
    f["camada_deterministica"] = f.ne_ccor.map(det.camada)

    def resultado(ted: str, d: object, cam: object) -> str:
        if not isinstance(d, str) or str(cam).startswith("6"):
            return "sem evidência"
        if d == ted:
            return "confirmado"
        return "contém" if ted in d.split(" + ") else "diverge"

    f["resultado"] = [
        resultado(t, d, c)
        for t, d, c in zip(f.ted, f.ted_deterministico, f.camada_deterministica)
    ]
    pd.set_option("display.width", 250)
    print(
        f.groupby("resultado")
        .agg(nes=("ne_ccor", "nunique"), empenhado=("emp", "sum"))
        .round(2)
    )
    print(f[f.resultado != "confirmado"].round(2).to_string(index=False))
    f.to_csv(
        SAIDA + "verificacao_similaridade.csv",
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig",
    )
