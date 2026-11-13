"""Testes de ``ClienteSiconv``: um zip por tabela no endereço novo do Transferegov.

O download é simulado (``requests.get``); a leitura usa um zip real gravado em
``utf-8-sig`` com ``;``, como a fonte publica.
"""

import os
import zipfile
from pathlib import Path
import glob
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import requests

from cliente_siconv import ClienteSiconv
from tabelas_siconv import TABELAS_SICONV


def _zip(tmp_path: Path, nome_csv: str, *linhas: str) -> str:
    caminho = tmp_path / "tabela.zip"
    conteudo = "".join(f"{linha}\r\n" for linha in linhas)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr(nome_csv, conteudo.encode("utf-8-sig"))
    return str(caminho)


def _resposta(
    conteudo: bytes = b"PK", status: int = 200, tamanho_anunciado: int = None
) -> MagicMock:
    resposta = MagicMock()
    resposta.__enter__.return_value = resposta
    resposta.iter_content.return_value = [conteudo]
    resposta.headers = {
        "Content-Length": str(
            len(conteudo) if tamanho_anunciado is None else tamanho_anunciado
        )
    }
    if status >= 400:
        resposta.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    return resposta


def _temporarios() -> set:
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "siconv_*.zip")))


def test_url_zip_troca_extensao_do_csv():
    url = ClienteSiconv().url_zip("siconv_desbloqueio_cr.csv")

    assert url == (
        "https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/"
        "siconv_desbloqueio_cr.zip"
    )


@pytest.mark.parametrize("tabela", TABELAS_SICONV, ids=lambda t: t["nome_tabela"])
def test_toda_tabela_aponta_para_um_zip_proprio(tabela):
    assert tabela["nome_csv"].startswith("siconv_")
    assert (
        ClienteSiconv()
        .url_zip(tabela["nome_csv"])
        .endswith(tabela["nome_csv"].replace(".csv", ".zip"))
    )


def test_tabela_com_filtro_tem_o_id_na_primeira_coluna():
    # A DAG filtra pela primeira coluna de "colunas".
    for tabela in TABELAS_SICONV:
        if tabela.get("filtro_ids_sql"):
            assert tabela["colunas"][0] == tabela["primary_key"][0].upper()


@patch("cliente_siconv.requests.get")
def test_baixar_zip_grava_arquivo_temporario(mock_get):
    mock_get.return_value = _resposta(b"conteudo do zip")
    cliente = ClienteSiconv()

    caminho = cliente.baixar_zip("siconv_convenio.csv")

    try:
        assert Path(caminho).read_bytes() == b"conteudo do zip"
        assert mock_get.call_args.args[0] == cliente.url_zip("siconv_convenio.csv")
    finally:
        os.remove(caminho)


@patch("cliente_siconv.requests.get")
def test_baixar_zip_em_paralelo_nao_compartilha_arquivo(mock_get):
    mock_get.return_value = _resposta()
    cliente = ClienteSiconv()

    a = cliente.baixar_zip("siconv_convenio.csv")
    b = cliente.baixar_zip("siconv_proposta.csv")

    try:
        assert a != b
    finally:
        os.remove(a)
        os.remove(b)


@patch("cliente_siconv.requests.get")
def test_baixar_zip_propaga_erro_http(mock_get):
    mock_get.return_value = _resposta(status=404)

    with pytest.raises(requests.HTTPError):
        ClienteSiconv().baixar_zip("siconv_convenio.csv")


@patch("cliente_siconv.requests.get")
def test_baixar_zip_apaga_arquivo_se_a_conexao_cai(mock_get):
    resposta = _resposta()
    resposta.iter_content.side_effect = requests.exceptions.ChunkedEncodingError()
    mock_get.return_value = resposta
    antes = _temporarios()

    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        ClienteSiconv().baixar_zip("siconv_convenio.csv")

    assert _temporarios() == antes


@patch("cliente_siconv.requests.get")
def test_baixar_zip_recusa_download_incompleto(mock_get):
    # O requests não acusa a conexão fechada antes do Content-Length.
    mock_get.return_value = _resposta(b"PK", tamanho_anunciado=100_000)
    antes = _temporarios()

    with pytest.raises(IOError, match="incompleto"):
        ClienteSiconv().baixar_zip("siconv_convenio.csv")

    assert _temporarios() == antes


def test_ler_csv_seleciona_colunas_esperadas_em_minusculas(tmp_path):
    caminho = _zip(
        tmp_path,
        "siconv_ingresso_contrapartida.csv",
        "NR_CONVENIO;DT_INGRESSO_CONTRAPARTIDA;VL_INGRESSO_CONTRAPARTIDA;EXTRA",
        "965092;10/02/2025;15239,11;x",
    )

    registros = list(
        ClienteSiconv().ler_csv(
            caminho,
            "siconv_ingresso_contrapartida.csv",
            colunas_esperadas=["NR_CONVENIO", "VL_INGRESSO_CONTRAPARTIDA"],
        )
    )

    assert registros == [
        {"nr_convenio": "965092", "vl_ingresso_contrapartida": "15239,11"}
    ]


def test_ler_csv_falha_quando_falta_coluna(tmp_path):
    caminho = _zip(tmp_path, "siconv_convenio.csv", "NR_CONVENIO", "965092")

    with pytest.raises(ValueError, match="ID_PROPOSTA"):
        list(
            ClienteSiconv().ler_csv(
                caminho,
                "siconv_convenio.csv",
                colunas_esperadas=["NR_CONVENIO", "ID_PROPOSTA"],
            )
        )


def test_ler_csv_pula_linhas(tmp_path):
    caminho = _zip(tmp_path, "siconv_convenio.csv", "NR_CONVENIO", "1", "2", "3")

    registros = list(ClienteSiconv().ler_csv(caminho, "siconv_convenio.csv", 2))

    assert registros == [{"nr_convenio": "3"}]
