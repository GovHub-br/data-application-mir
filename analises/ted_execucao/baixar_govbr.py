"""Baixa as subpáginas por ano de transferências voluntárias do MIR no gov.br."""

import re
import time

import httpx

from govbr_pagina import PASTA

BASE = (
    "https://www.gov.br/igualdaderacial/pt-br/acesso-a-informacao/"
    "convenios-e-transferencias/tranferencias-voluntarias"
)

if __name__ == "__main__":
    import os

    os.makedirs(PASTA, exist_ok=True)
    cliente = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=60
    )
    principal = cliente.get(BASE).text
    paginas = list(
        dict.fromkeys(
            re.findall(
                r'href="[^"]*/tranferencias-voluntarias/(\d{4}(?:-\d+)?)/?"', principal
            )
        )
    )
    for p in paginas:
        open(f"{PASTA}{p}.html", "w").write(cliente.get(f"{BASE}/{p}").text)
        print(p)
        time.sleep(1)
