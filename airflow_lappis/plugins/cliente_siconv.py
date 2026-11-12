import zipfile
import csv
import io
import logging
import os
import tempfile
import requests

class ClienteSiconv:
    # Desde 07/2026 o Transferegov publica um zip por tabela (Download de Dados do
    # módulo Discricionárias e Legais); o siconv.zip único do repositorio.dados.gov.br
    # deixou de ser atualizado em 17/07/2026 e depois saiu do ar.
    URL_BASE = "https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov"

    def url_zip(self, nome_csv: str) -> str:
        """URL do zip da tabela: siconv_convenio.csv -> .../siconv_convenio.zip."""
        nome_zip = os.path.splitext(nome_csv)[0] + ".zip"
        return f"{self.URL_BASE}/{nome_zip}"

    def baixar_zip(self, nome_csv: str) -> str:
        """Baixa o zip da tabela para um arquivo temporário e devolve o caminho."""
        url = self.url_zip(nome_csv)
        logging.info(f"[cliente_siconv.py] Baixando {url}...")
        response = requests.get(url, stream=True, timeout=(30, 300))
        response.raise_for_status()
        fd, zip_path = tempfile.mkstemp(prefix="siconv_", suffix=".zip")
        with os.fdopen(fd, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        logging.info("[cliente_siconv.py] Download concluído")
        return zip_path

    def ler_csv(
        self,
        zip_path: str,
        nome_csv: str,
        skip_rows: int = 0,
        colunas_esperadas: list = None,
    ):
        logging.info(f"[cliente_siconv.py] Lendo {nome_csv} em modo streaming...")
        with zipfile.ZipFile(zip_path, "r") as z:
            with z.open(nome_csv) as f:
                conteudo = io.TextIOWrapper(f, encoding="utf-8-sig")
                reader = csv.DictReader(conteudo, delimiter=";")

                if colunas_esperadas:
                    colunas_csv = reader.fieldnames or []
                    faltando = [c for c in colunas_esperadas if c not in colunas_csv]
                    if faltando:
                        raise ValueError(f"[cliente_siconv.py] Colunas faltando em {nome_csv}: {faltando}")

                for i, row in enumerate(reader):
                    if i < skip_rows:
                        continue

                    if colunas_esperadas:
                        yield {k.lower(): row[k] for k in colunas_esperadas}
                    else:
                        yield {k.lower(): v for k, v in row.items() if k is not None}
