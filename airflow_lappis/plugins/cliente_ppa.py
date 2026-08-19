import csv
import hashlib
import io
import logging
import re
import unicodedata
import zipfile
from typing import Iterator, Optional

import requests


class ClientePPA:
    """Cliente de extração dos dados abertos do PPA/SIOP.

    Segue a arquitetura do ``ClienteSiconv`` (download do ``.zip`` + leitura de
    cada CSV em streaming de dentro do zip), com as adaptações que a fonte do PPA
    exige:

    - cada instância representa **uma revisão/ano** do PPA (``ano_ppa``), ligada
      ao respectivo ``.zip``;
    - os CSVs vêm em **latin-1** (não utf-8) e com cabeçalhos "humanos"
      (com acentos, espaços e pontuação), que são normalizados para
      identificadores ``snake_case`` ASCII válidos no Postgres;
    - cada registro é enriquecido com ``ano_ppa`` (versão de origem) e
      ``id_hash`` (surrogate = md5 das colunas de negócio + ano), usado como
      chave de conflito para tornar a reingestão idempotente.
    """

    ENCODING = "latin-1"
    DELIMITER = ";"

    def __init__(self, ano_ppa: int, url: Optional[str] = None) -> None:
        self.ano_ppa = int(ano_ppa)
        self.url = url
        self.zip_path = f"/tmp/ppa_{self.ano_ppa}.zip"

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #
    def baixar_zip(self) -> str:
        if not self.url:
            raise ValueError(
                "[cliente_ppa.py] URL não informada para o ano "
                f"{self.ano_ppa}; não é possível baixar o zip."
            )

        logging.info("[cliente_ppa.py] Baixando PPA %s de %s ...", self.ano_ppa, self.url)
        response = requests.get(self.url, stream=True)
        response.raise_for_status()
        with open(self.zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info("[cliente_ppa.py] Download concluído em %s", self.zip_path)
        return self.zip_path

    # ------------------------------------------------------------------ #
    # Normalização de colunas
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalizar_coluna(nome: str) -> str:
        """Converte um cabeçalho humano em identificador snake_case ASCII.

        Ex.: ``"Despesa Corrente - 1º ano PPA"`` -> ``despesa_corrente_1o_ano_ppa``.
        """
        decomposto = unicodedata.normalize("NFKD", nome)
        sem_acentos = "".join(c for c in decomposto if not unicodedata.combining(c))
        slug = re.sub(r"[^0-9a-zA-Z]+", "_", sem_acentos).strip("_").lower()
        return slug or "coluna"

    def _nomes_colunas(self, cabecalho: list) -> list:
        """Mapeia o cabeçalho para nomes de coluna, preservando a posição.

        Colunas vazias (ex.: o ``;`` final que gera um campo em branco) viram
        ``None`` para serem ignoradas sem desalinhar as demais. Nomes repetidos
        recebem sufixo numérico.
        """
        nomes: list = []
        vistos: dict = {}
        for bruto in cabecalho:
            if not bruto or not bruto.strip():
                nomes.append(None)
                continue
            slug = self.normalizar_coluna(bruto)
            if slug in vistos:
                vistos[slug] += 1
                slug = f"{slug}_{vistos[slug]}"
            else:
                vistos[slug] = 1
            nomes.append(slug)
        return nomes

    @staticmethod
    def _id_hash(registro: dict) -> str:
        base = "||".join(f"{chave}={registro[chave]}" for chave in sorted(registro))
        return hashlib.md5(base.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ #
    # Leitura de CSV em streaming
    # ------------------------------------------------------------------ #
    def ler_csv(
        self,
        nome_arquivo: str,
        skip_rows: int = 0,
        colunas_esperadas: Optional[list] = None,
    ) -> Iterator[dict]:
        """Itera os registros do CSV ``{nome_arquivo}_{ano_ppa}.csv`` do zip.

        Cada registro sai como ``dict`` já com colunas normalizadas, mais
        ``ano_ppa`` e ``id_hash``.
        """
        alvo = f"{nome_arquivo}_{self.ano_ppa}.csv"
        logging.info("[cliente_ppa.py] Lendo %s em modo streaming...", alvo)

        with zipfile.ZipFile(self.zip_path, "r") as z:
            try:
                interno = next(n for n in z.namelist() if n.split("/")[-1] == alvo)
            except StopIteration:
                raise FileNotFoundError(
                    f"[cliente_ppa.py] '{alvo}' não encontrado em {self.zip_path}"
                )

            with z.open(interno) as f:
                conteudo = io.TextIOWrapper(f, encoding=self.ENCODING, newline="")
                reader = csv.reader(conteudo, delimiter=self.DELIMITER)

                try:
                    cabecalho = next(reader)
                except StopIteration:
                    return

                nomes = self._nomes_colunas(cabecalho)

                if colunas_esperadas:
                    presentes = [n for n in nomes if n is not None]
                    faltando = [c for c in colunas_esperadas if c not in presentes]
                    if faltando:
                        raise ValueError(
                            f"[cliente_ppa.py] Colunas faltando em {alvo}: {faltando}"
                        )

                for i, linha in enumerate(reader):
                    if i < skip_rows:
                        continue
                    if not any(valor.strip() for valor in linha):
                        continue

                    registro: dict = {
                        nome: valor
                        for nome, valor in zip(nomes, linha)
                        if nome is not None
                    }
                    registro["ano_ppa"] = self.ano_ppa
                    registro["id_hash"] = self._id_hash(registro)
                    yield registro
