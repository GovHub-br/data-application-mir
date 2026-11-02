import csv
import hashlib
import io
import json
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
      ``id_hash`` (surrogate = md5 de uma serialização injetiva das colunas de
      negócio + ano), usado como chave de conflito para tornar a reingestão
      idempotente.
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

        O resultado é um identificador **válido sem quote** no Postgres, porque
        o DDL de ``cliente_postgres.py`` interpola a coluna direto
        (``f"{column} TEXT"``). Daí as duas correções de borda: um cabeçalho
        sem nenhum alfanumérico (``"###"``) viraria string vazia e recebe o
        nome ``coluna``; um que comece por dígito (``"1º ano"``) recebe ``_``
        na frente, já que identificador não pode começar por número.
        """
        decomposto = unicodedata.normalize("NFKD", nome)
        sem_acentos = "".join(c for c in decomposto if not unicodedata.combining(c))
        slug = re.sub(r"[^0-9a-zA-Z]+", "_", sem_acentos).strip("_").lower() or "coluna"
        return f"_{slug}" if slug[0].isdigit() else slug

    @staticmethod
    def _nome_livre(slug: str, vistos: dict) -> str:
        """Devolve ``slug``, ou o primeiro sufixado que ainda não esteja em uso.

        Não basta sufixar com a contagem de ocorrências: o nome sufixado pode
        já existir por conta própria no cabeçalho (``["Ano", "Ano", "Ano 2"]``),
        e aí duas colunas receberiam ``ano_2`` e uma sobrescreveria a outra no
        registro. Por isso a busca avança até achar um nome realmente livre.
        """
        if slug not in vistos:
            return slug

        candidato = slug
        while candidato in vistos:
            vistos[slug] += 1
            candidato = f"{slug}_{vistos[slug]}"
        return candidato

    def _nomes_colunas(self, cabecalho: list) -> list:
        """Mapeia o cabeçalho para nomes de coluna, preservando a posição.

        Colunas vazias (ex.: o ``;`` final que gera um campo em branco) viram
        ``None`` para serem ignoradas sem desalinhar as demais. Nomes repetidos
        recebem sufixo numérico, garantidamente único no cabeçalho.
        """
        nomes: list = []
        vistos: dict = {}
        for bruto in cabecalho:
            if not bruto or not bruto.strip():
                nomes.append(None)
                continue
            slug = self._nome_livre(self.normalizar_coluna(bruto), vistos)
            vistos[slug] = 1
            nomes.append(slug)
        return nomes

    @staticmethod
    def _alinhar(linha: list, nomes: list, alvo: str, n_linha: int) -> list:
        """Ajusta a linha à aridade do cabeçalho, ou falha se houver excedente.

        O ``zip(nomes, linha)`` que monta o registro para no mais curto dos
        dois, então sem esta checagem a aridade errada passa em silêncio:

        - campos **a mais** significam que o CSV não corresponde ao cabeçalho
          (ex.: um ``;`` não escapado dentro de um campo de texto). Descartar o
          excedente perderia dado, então é erro, com a posição no arquivo para
          o diagnóstico;
        - campos **a menos** acontecem quando a fonte omite o ``;`` final. São
          completados com vazio, para que a linha curta e a linha completa
          rendam o mesmo registro e o mesmo ``id_hash``.
        """
        if len(linha) > len(nomes):
            raise ValueError(
                f"[cliente_ppa.py] Linha {n_linha} de {alvo}: o cabeçalho tem "
                f"{len(nomes)} colunas, mas a linha tem {len(linha)} campos"
            )
        if len(linha) < len(nomes):
            return linha + [""] * (len(nomes) - len(linha))
        return linha

    @staticmethod
    def _id_hash(registro: dict) -> str:
        """Surrogate idempotente do registro (md5 das colunas + ``ano_ppa``).

        A string base é uma serialização **injetiva** do registro: dois
        registros diferentes nunca produzem a mesma base. Por isso ela usa JSON
        em vez de concatenar ``chave=valor`` com um separador — um valor que
        contivesse o separador colidiria com outro registro, e como o
        ``id_hash`` é a chave de conflito do upsert, um dos dois seria perdido
        em silêncio.
        """
        base = json.dumps(
            [[chave, registro[chave]] for chave in sorted(registro)],
            ensure_ascii=False,
            separators=(",", ":"),
        )
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

        Args:
            nome_arquivo: basename do CSV no zip, sem o sufixo ``_{ano}.csv``.
            skip_rows: linhas de dados a descartar após o cabeçalho (contadas
                antes do descarte de linhas em branco).
            colunas_esperadas: se informado, o cabeçalho tem de conter todas.

        Raises:
            FileNotFoundError: o CSV do ano não está no zip.
            ValueError: o cabeçalho não rende nenhuma coluna nomeada, falta
                alguma das ``colunas_esperadas``, ou alguma linha tem mais
                campos que o cabeçalho.
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

                if not any(nome is not None for nome in nomes):
                    raise ValueError(
                        f"[cliente_ppa.py] {alvo} não rendeu nenhuma coluna "
                        f"nomeada; primeira linha do arquivo: {cabecalho!r}"
                    )

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

                    linha = self._alinhar(linha, nomes, alvo, i + 2)

                    registro: dict = {
                        nome: valor
                        for nome, valor in zip(nomes, linha)
                        if nome is not None
                    }
                    registro["ano_ppa"] = self.ano_ppa
                    registro["id_hash"] = self._id_hash(registro)
                    yield registro
