"""Testes de ``ClientePPA.ler_csv`` combinando caixa-preta e caixa-branca.

Trabalho PTOSS-2 (FGA 0314 — Testes de Software). O método ``ler_csv`` é o
ponto de entrada da ingestão do PPA/SIOP (issue #477) e estava com 0% de
cobertura. Os testes foram projetados nos dois sentidos pedidos pela
especificação do trabalho:

- **Caixa-preta -> caixa-branca** em ``ler_csv``: os casos ``CP*`` saem da
  especificação (docstring do módulo e do método: zip + CSV em latin-1,
  colunas normalizadas, ``ano_ppa`` e ``id_hash`` por registro), por
  particionamento de equivalência e análise de valor limite. Depois os casos
  ``CB*`` completam com os ramos que a especificação não descreve.
- **Caixa-branca -> caixa-preta** em ``_nomes_colunas`` e ``normalizar_coluna``:
  os casos ``MCDC*`` saem da decisão composta ``not bruto or not bruto.strip()``
  e do ``any(...)`` do descarte de linhas em branco, pelo critério MC/DC com
  curto-circuito. Depois a análise de valor limite completa com as fronteiras
  do slug e da deduplicação de nomes.

Nenhuma resposta é simulada: os testes montam um ``.zip`` real com bytes
``latin-1`` reais, então ``zipfile``, ``TextIOWrapper`` e ``csv.reader`` rodam
com o comportamento de produção. Só o ``zip_path`` é apontado para o arquivo
temporário do teste, no lugar do download.

Os cinco defeitos encontrados no código de produção estão registrados como
``xfail(strict=True)`` — documentam o problema sem quebrar a suíte e passam a
falhar se alguém corrigir o código sem remover a marcação. A correção via TDD
é a segunda parte do trabalho.
"""

import zipfile
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, patch

import pytest
import requests

from cliente_ppa import ClientePPA

ANO = 2024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cliente(
    tmp_path: Path,
    conteudo: str,
    nome_no_zip: str = f"tabela_{ANO}.csv",
    ano: int = ANO,
) -> ClientePPA:
    """``ClientePPA`` apontado para um zip real gravado em ``latin-1``."""
    cliente = ClientePPA(ano_ppa=ano)
    tmp_path.mkdir(parents=True, exist_ok=True)
    cliente.zip_path = str(tmp_path / f"ppa_{ano}.zip")
    with zipfile.ZipFile(cliente.zip_path, "w") as z:
        z.writestr(nome_no_zip, conteudo.encode(ClientePPA.ENCODING))
    return cliente


def _csv(*linhas: str) -> str:
    """Monta o CSV com o terminador de linha que a fonte usa."""
    return "".join(f"{linha}\r\n" for linha in linhas)


def _negocio(registro: dict) -> dict:
    """Só as colunas de negócio, sem os campos acrescentados pelo cliente."""
    return {
        chave: valor
        for chave, valor in registro.items()
        if chave not in ("ano_ppa", "id_hash")
    }


def _ler(
    cliente: ClientePPA,
    skip_rows: int = 0,
    colunas_esperadas: Optional[list] = None,
) -> list:
    return list(
        cliente.ler_csv(
            "tabela", skip_rows=skip_rows, colunas_esperadas=colunas_esperadas
        )
    )


# ===========================================================================
# CAIXA-PRETA — casos derivados da especificação
# ===========================================================================


# --- Condição 1: localização do CSV dentro do zip --------------------------
def test_CP1a_csv_na_raiz_do_zip(tmp_path: Path) -> None:
    """CE1: ``{nome}_{ano}.csv`` na raiz do zip é lido."""
    cliente = _cliente(tmp_path, _csv("Codigo;Nome", "01;Programa A"))

    assert [_negocio(r) for r in _ler(cliente)] == [
        {"codigo": "01", "nome": "Programa A"}
    ]


def test_CP1b_csv_em_subpasta_e_localizado_pelo_basename(tmp_path: Path) -> None:
    """CE2: o zip do SIOP aninha os CSVs; o match é por basename."""
    cliente = _cliente(
        tmp_path, _csv("Codigo", "01"), nome_no_zip=f"PPA_{ANO}/tabela_{ANO}.csv"
    )

    assert [_negocio(r) for r in _ler(cliente)] == [{"codigo": "01"}]


@pytest.mark.parametrize(
    "nome_no_zip",
    [
        pytest.param("outra_coisa.csv", id="CE3-ausente"),
        pytest.param(f"tabela_{ANO + 1}.csv", id="CE4-so-outro-ano"),
        pytest.param(f"xtabela_{ANO}.csv", id="limite-sufixo"),
        pytest.param(f"tabela_{ANO}.csv.bkp", id="limite-prefixo"),
    ],
)
def test_CP1c_csv_do_ano_ausente_levanta_filenotfound(
    tmp_path: Path, nome_no_zip: str
) -> None:
    """CE3/CE4 e os limites do casamento de nome: nada de match parcial.

    ``xtabela_2024.csv`` e ``tabela_2024.csv.bkp`` são os vizinhos imediatos
    do nome exato — garantem que a busca não aceita sufixo nem prefixo.
    """
    cliente = _cliente(tmp_path, _csv("Codigo", "01"), nome_no_zip=nome_no_zip)

    with pytest.raises(FileNotFoundError, match=f"tabela_{ANO}.csv"):
        _ler(cliente)


# --- Condição 2: quantidade de linhas de dados ----------------------------
def test_CP2a_arquivo_de_zero_bytes_retorna_sem_registros(tmp_path: Path) -> None:
    """CE7 (limite inferior, 0 bytes): encerra sem erro, sem registros."""
    cliente = _cliente(tmp_path, "")

    assert _ler(cliente) == []


def test_CP2b_apenas_cabecalho_retorna_sem_registros(tmp_path: Path) -> None:
    """CE8 (limite 0 linhas de dados): cabeçalho consumido, nada rendido."""
    cliente = _cliente(tmp_path, _csv("Codigo;Nome"))

    assert _ler(cliente) == []


@pytest.mark.parametrize("n_linhas", [1, 2, 3])
def test_CP2c_quantidade_de_registros_acompanha_as_linhas(
    tmp_path: Path, n_linhas: int
) -> None:
    """CE5/CE6 nos limites 1, 2 e 3 linhas de dados."""
    linhas = [f"{i:02d}" for i in range(1, n_linhas + 1)]
    cliente = _cliente(tmp_path, _csv("Codigo", *linhas))

    assert [r["codigo"] for r in _ler(cliente)] == linhas


# --- Condição 3: forma do cabeçalho ---------------------------------------
def test_CP3a_cabecalho_humano_vira_snake_case_ascii(tmp_path: Path) -> None:
    """CE9: acentos, espaços e pontuação viram identificador snake_case."""
    cliente = _cliente(
        tmp_path,
        _csv("Código;Objetivo Específico;Despesa Corrente - 1 ano PPA", "01;Obj;10"),
    )

    assert list(_negocio(_ler(cliente)[0])) == [
        "codigo",
        "objetivo_especifico",
        "despesa_corrente_1_ano_ppa",
    ]


def test_CP3b_campo_vazio_no_cabecalho_e_ignorado_sem_desalinhar(
    tmp_path: Path,
) -> None:
    """CE10: o ``;`` final do SIOP gera um campo em branco.

    A coluna vazia tem de ser descartada **sem** deslocar as demais — por isso
    o teste confere o valor de cada coluna, não só os nomes.
    """
    cliente = _cliente(tmp_path, _csv("Codigo;;Nome;", "01;lixo;Programa A;"))

    assert _negocio(_ler(cliente)[0]) == {"codigo": "01", "nome": "Programa A"}


def test_CP3c_cabecalho_repetido_recebe_sufixo_numerico(tmp_path: Path) -> None:
    """CE11: nomes repetidos são desambiguados por sufixo."""
    cliente = _cliente(tmp_path, _csv("Ano;Ano;Ano", "1;2;3"))

    assert _negocio(_ler(cliente)[0]) == {"ano": "1", "ano_2": "2", "ano_3": "3"}


# --- Condição 4: skip_rows ------------------------------------------------
def test_CP4a_skip_rows_default_nao_descarta_nada(tmp_path: Path) -> None:
    """CE12 (limite inferior, 0): nenhuma linha de dados é perdida."""
    cliente = _cliente(tmp_path, _csv("Codigo", "01", "02"))

    assert [r["codigo"] for r in _ler(cliente)] == ["01", "02"]


@pytest.mark.parametrize(
    ("skip_rows", "esperado"),
    [
        pytest.param(1, ["02", "03"], id="CE13-primeira"),
        pytest.param(2, ["03"], id="CE13-duas"),
        pytest.param(3, [], id="limite-total"),
        pytest.param(4, [], id="CE14-acima-do-total"),
    ],
)
def test_CP4b_skip_rows_descarta_as_primeiras_linhas(
    tmp_path: Path, skip_rows: int, esperado: list
) -> None:
    """CE13/CE14 nos limites 1, 2, total e total+1 (3 linhas de dados)."""
    cliente = _cliente(tmp_path, _csv("Codigo", "01", "02", "03"))

    assert [r["codigo"] for r in _ler(cliente, skip_rows=skip_rows)] == esperado


# --- Condição 5: colunas_esperadas ----------------------------------------
@pytest.mark.parametrize(
    "colunas_esperadas",
    [
        pytest.param(None, id="CE15-none"),
        pytest.param([], id="CE16-lista-vazia"),
    ],
)
def test_CP5a_colunas_esperadas_falsy_dispensa_validacao(
    tmp_path: Path, colunas_esperadas: Optional[list]
) -> None:
    """CE15/CE16: sem contrato declarado, lê o que vier."""
    cliente = _cliente(tmp_path, _csv("Qualquer", "1"))

    assert _negocio(_ler(cliente, colunas_esperadas=colunas_esperadas)[0]) == {
        "qualquer": "1"
    }


@pytest.mark.parametrize(
    "colunas_esperadas",
    [
        pytest.param(["codigo"], id="limite-uma"),
        pytest.param(["codigo", "nome"], id="CE17-todas"),
    ],
)
def test_CP5b_colunas_esperadas_presentes_seguem_a_leitura(
    tmp_path: Path, colunas_esperadas: list
) -> None:
    """CE17: o subconjunto e o conjunto completo são aceitos."""
    cliente = _cliente(tmp_path, _csv("Codigo;Nome", "01;A"))

    assert len(_ler(cliente, colunas_esperadas=colunas_esperadas)) == 1


def test_CP5c_coluna_faltando_levanta_valueerror_nomeando_a_coluna(
    tmp_path: Path,
) -> None:
    """CE18: a mensagem tem de nomear só o que falta, para o diagnóstico."""
    cliente = _cliente(tmp_path, _csv("Codigo;Nome", "01;A"))

    with pytest.raises(ValueError, match=r"Colunas faltando.*\['valor'\]"):
        _ler(cliente, colunas_esperadas=["codigo", "valor"])


def test_CP5d_coluna_esperada_em_campo_vazio_conta_como_faltando(
    tmp_path: Path,
) -> None:
    """Limite: a coluna existe na posição, mas sem nome -> vira ``None``.

    Caso de fronteira entre CE10 (campo vazio ignorado) e CE18 (coluna
    faltando): uma coluna sem cabeçalho não satisfaz o contrato.
    """
    cliente = _cliente(tmp_path, _csv("Codigo;;Valor", "01;x;10"))

    with pytest.raises(ValueError, match=r"\['nome'\]"):
        _ler(cliente, colunas_esperadas=["codigo", "nome", "valor"])


# --- Condição 6: linhas em branco -----------------------------------------
@pytest.mark.parametrize(
    "linha",
    [
        pytest.param(";;", id="CE20-todos-vazios"),
        pytest.param("  ;  ;  ", id="CE21-so-espacos"),
        pytest.param("\t;\t;\t", id="CE21-so-tabs"),
    ],
)
def test_CP6a_linha_em_branco_e_descartada(tmp_path: Path, linha: str) -> None:
    """CE20/CE21: o rodapé em branco do CSV não pode virar registro."""
    cliente = _cliente(tmp_path, _csv("A;B;C", "1;2;3", linha))

    assert len(_ler(cliente)) == 1


@pytest.mark.parametrize(
    ("linha", "esperado"),
    [
        pytest.param(";;x", {"a": "", "b": "", "c": "x"}, id="limite-ultima"),
        pytest.param("x;;", {"a": "x", "b": "", "c": ""}, id="limite-primeira"),
        pytest.param(";0;", {"a": "", "b": "0", "c": ""}, id="limite-zero"),
    ],
)
def test_CP6b_um_unico_campo_preenchido_mantem_a_linha(
    tmp_path: Path, linha: str, esperado: dict
) -> None:
    """CE19 (limite: 1 caractere não branco): a linha é dado, não rodapé.

    O caso ``;0;`` é a fronteira que separa "campo vazio" de "campo falsy":
    ``"0"`` é falsy em muitas linguagens, mas é dado do PPA.
    """
    cliente = _cliente(tmp_path, _csv("A;B;C", linha))

    assert _negocio(_ler(cliente)[0]) == esperado


# --- Condição 7: encoding -------------------------------------------------
def test_CP7_valores_em_latin1_sao_decodificados(tmp_path: Path) -> None:
    """CE22: a fonte publica em latin-1, não utf-8."""
    cliente = _cliente(tmp_path, _csv("Descricao", "Ação Orçamentária - Região Centro"))

    assert _ler(cliente)[0]["descricao"] == "Ação Orçamentária - Região Centro"


# --- Condição 8: campos acrescentados pelo cliente ------------------------
def test_CP8a_todo_registro_recebe_ano_ppa_inteiro(tmp_path: Path) -> None:
    """CE23: ``ano_ppa`` identifica a revisão de origem e é ``int``."""
    cliente = _cliente(tmp_path, _csv("Codigo", "01", "02"))

    for registro in _ler(cliente):
        assert registro["ano_ppa"] == ANO
        assert isinstance(registro["ano_ppa"], int)


def test_CP8b_id_hash_e_estavel_entre_releituras(tmp_path: Path) -> None:
    """CE24: a reingestão do mesmo zip tem de gerar as mesmas chaves."""
    cliente = _cliente(tmp_path, _csv("Codigo;Nome", "01;A", "02;B"))

    primeira = [r["id_hash"] for r in _ler(cliente)]
    segunda = [r["id_hash"] for r in _ler(cliente)]

    assert primeira == segunda


def test_CP8c_id_hash_difere_entre_revisoes_do_ppa(tmp_path: Path) -> None:
    """CE25: o mesmo registro em dois anos coexiste na tabela empilhada."""
    hashes = set()
    for ano in (2024, 2025):
        cliente = _cliente(
            tmp_path,
            _csv("Codigo;Nome", "01;A"),
            nome_no_zip=f"tabela_{ano}.csv",
            ano=ano,
        )
        hashes.add(_ler(cliente)[0]["id_hash"])

    assert len(hashes) == 2


def test_CP8d_registros_distintos_recebem_id_hash_distinto(tmp_path: Path) -> None:
    """CE24: a chave de conflito do upsert só pode colidir em registro igual."""
    cliente = _cliente(tmp_path, _csv("Codigo;Nome", "01;A", "02;B", "01;B"))

    registros = _ler(cliente)

    assert len({r["id_hash"] for r in registros}) == len(registros)


# ===========================================================================
# CAIXA-BRANCA -> CAIXA-PRETA — MC/DC das decisões compostas
# ===========================================================================


# Decisão D12 (cliente_ppa.py:81) ``not bruto or not bruto.strip()``
#   A: not bruto            B: not bruto.strip()
# Caso | entrada | A | B | D12 | nome da coluna
# MC1  | "Ano"   | F | F |  F  | "ano"
# MC2  | ""      | V | - |  V  | None   (B em curto-circuito)
# MC3  | "   "   | F | V |  V  | None
# Pares de independência: A por (MC1, MC2); B por (MC1, MC3).
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        pytest.param("Ano", "ano", id="MC1-A_F-B_F"),
        pytest.param("", None, id="MC2-A_V"),
        pytest.param("   ", None, id="MC3-A_F-B_V"),
    ],
)
def test_MCDC_D12_cabecalho_em_branco_vira_none(
    entrada: str, esperado: Optional[str]
) -> None:
    """MC/DC de ``not bruto or not bruto.strip()`` com curto-circuito.

    São n+1 = 3 casos para 2 condições. Em MC2 a condição B não é avaliada,
    o que o MC/DC com curto-circuito aceita.
    """
    cliente = ClientePPA(ano_ppa=ANO)

    assert cliente._nomes_colunas([entrada]) == [esperado]


# Decisão D9 (cliente_ppa.py:145) ``not any(valor.strip() for valor in linha)``
# Para um cabeçalho de 3 colunas o ``any`` é a disjunção v1 ∨ v2 ∨ v3.
# Caso | linha  | v1 | v2 | v3 | any | registro?
# MD1  | x;;    |  V | -  | -  |  V  | sim
# MD2  | ;;     |  F | F  | F  |  F  | não
# MD3  | ;y;    |  F | V  | -  |  V  | sim
# MD4  | ;;z    |  F | F  | V  |  V  | sim
# Pares: v1 por (MD1, MD2); v2 por (MD3, MD2); v3 por (MD4, MD2).
@pytest.mark.parametrize(
    ("linha", "rende_registro"),
    [
        pytest.param("x;;", True, id="MD1-v1_V"),
        pytest.param(";;", False, id="MD2-todas_F"),
        pytest.param(";y;", True, id="MD3-v2_V"),
        pytest.param(";;z", True, id="MD4-v3_V"),
    ],
)
def test_MCDC_D9_descarte_de_linha_em_branco(
    tmp_path: Path, linha: str, rende_registro: bool
) -> None:
    """MC/DC do ``any`` do descarte de linhas, com curto-circuito.

    São n+1 = 4 casos para 3 condições; MD2 é o caso de referência que fixa
    as demais condições em falso.
    """
    cliente = _cliente(tmp_path, _csv("A;B;C", linha))

    assert len(_ler(cliente)) == (1 if rende_registro else 0)


# --- Complemento caixa-preta sobre o MC/DC: fronteiras do slug ------------
@pytest.mark.parametrize(
    ("cabecalho", "esperado"),
    [
        pytest.param("Ano", "ano", id="ja-normalizado"),
        pytest.param("  Ano  ", "ano", id="espacos-nas-pontas"),
        pytest.param("ÁÉÍÓÚ ãç", "aeiou_ac", id="acentos-e-cedilha"),
        pytest.param("Despesa - 1 ano", "despesa_1_ano", id="pontuacao-virando-_"),
        pytest.param("R$ (mil)", "r_mil", id="simbolos"),
        pytest.param("_Ano_", "ano", id="limite-underscore-nas-pontas"),
        pytest.param("###", "coluna", id="limite-slug-vazio"),
        pytest.param("_", "coluna", id="limite-so-underscore"),
    ],
)
def test_AVL_normalizar_coluna_nas_fronteiras_do_slug(
    cabecalho: str, esperado: str
) -> None:
    """AVL sobre o ``return slug or "coluna"`` (D15) e a limpeza de bordas.

    ``"###"`` e ``"_"`` são o limite inferior: tudo é descartado e sobra a
    string vazia, que ativa o literal ``"coluna"``. Note que ``"_"`` **não**
    cai no ramo de D12 (tem conteúdo após ``strip()``), por isso chega aqui.
    """
    assert ClientePPA.normalizar_coluna(cabecalho) == esperado


@pytest.mark.parametrize(
    ("cabecalho", "esperado"),
    [
        pytest.param(["Ano"], ["ano"], id="limite-1-ocorrencia"),
        pytest.param(["Ano", "Ano"], ["ano", "ano_2"], id="limite-2-ocorrencias"),
        pytest.param(
            ["Ano", "Ano", "Ano"], ["ano", "ano_2", "ano_3"], id="3-ocorrencias"
        ),
        pytest.param(["###", "###"], ["coluna", "coluna_2"], id="dedup-do-slug-vazio"),
        pytest.param(
            ["Ano", "ANO", "  ano  "], ["ano", "ano_2", "ano_3"], id="apos-slug"
        ),
    ],
)
def test_AVL_dedup_de_nomes_repetidos(cabecalho: list, esperado: list) -> None:
    """AVL sobre a decisão D13 (``if slug in vistos``).

    O limite é a 1ª vs. a 2ª ocorrência: só a partir da 2ª entra o sufixo. O
    caso ``["Ano", "ANO", "  ano  "]`` mostra que a colisão é avaliada
    **depois** da normalização, não sobre o texto bruto: as três grafias
    diferentes colidem no mesmo slug.
    """
    cliente = ClientePPA(ano_ppa=ANO)

    assert cliente._nomes_colunas(cabecalho) == esperado


# ===========================================================================
# CAIXA-BRANCA — ramos que nenhum caso da especificação alcança
# ===========================================================================
def test_CB1_skip_rows_conta_linhas_em_branco(tmp_path: Path) -> None:
    """Fixa a ordem entre D8 (``i < skip_rows``) e D9 (linha em branco).

    ``i`` enumera as linhas **cruas**, e o descarte de linha em branco vem
    depois. Então uma linha em branco entre as primeiras consome uma vaga do
    ``skip_rows``: aqui ``skip_rows=1`` queria descartar ``01``, mas gastou a
    vaga na linha em branco e ``01`` sobreviveu. É a semântica correta para o
    uso real (descartar sub-cabeçalhos posicionais), e este teste a trava
    contra mudança acidental.
    """
    cliente = _cliente(tmp_path, _csv("Codigo", ";", "01", "02"))

    assert [r["codigo"] for r in _ler(cliente, skip_rows=1)] == ["01", "02"]


def test_CB2_combining_filter_preserva_caractere_de_compatibilidade() -> None:
    """Cobre os dois lados do filtro de ``unicodedata.combining`` (D14).

    ``"º"`` não é combinante: o NFKD o decompõe por compatibilidade em ``"o"``,
    que **permanece**. Já o acento de ``"ç"`` é combinante e é removido. Sem
    este caso o ramo falso de D14 fica exercitado sem validação do resultado.
    """
    assert ClientePPA.normalizar_coluna("1º ano") == "1o_ano"
    assert ClientePPA.normalizar_coluna("Ação") == "acao"


def test_CB3_id_hash_cobre_todas_as_colunas_de_negocio() -> None:
    """Cobre o genexpr de ``_id_hash``: mudar qualquer coluna muda o hash."""
    base = {"codigo": "01", "nome": "A", "ano_ppa": ANO}

    hashes = {ClientePPA._id_hash(base)}
    for chave in base:
        alterado = dict(base, **{chave: "ZZZ"})
        hashes.add(ClientePPA._id_hash(alterado))

    assert len(hashes) == 1 + len(base)


# ===========================================================================
# DEFEITOS ENCONTRADOS NO CÓDIGO DE PRODUÇÃO
# ---------------------------------------------------------------------------
# Registrados como xfail(strict=True): documentam o defeito sem quebrar a
# suíte e falham se o código for corrigido sem remover a marcação. A correção
# por TDD é a parte 2 do trabalho.
# ===========================================================================
def test_TDD1_id_hash_nao_colide_quando_o_valor_contem_o_separador() -> None:
    """Conjuntos de colunas diferentes não podem compartilhar o hash."""
    um = {"a": "1||b=2"}
    outro = {"a": "1", "b": "2"}

    assert ClientePPA._id_hash(um) != ClientePPA._id_hash(outro)


def test_TDD1_registros_distintos_do_csv_nao_colidem(tmp_path: Path) -> None:
    """Duas linhas distintas do CSV têm de sair com ``id_hash`` distinto."""
    cliente = _cliente(
        tmp_path,
        _csv(
            "a;b;c",
            f"1||ano_ppa={ANO}||b=2;;9",
            f"1;2||ano_ppa={ANO}||b=;9",
        ),
    )

    registros = _ler(cliente)

    assert _negocio(registros[0]) != _negocio(registros[1])
    assert registros[0]["id_hash"] != registros[1]["id_hash"]


@pytest.mark.parametrize(
    "cabecalho",
    [
        pytest.param(["Ano", "Ano", "Ano 2"], id="sufixo-colide-com-nome-posterior"),
        pytest.param(["Ano 2", "Ano", "Ano"], id="sufixo-colide-com-nome-anterior"),
        pytest.param(["Ano", "Ano 2", "Ano"], id="sufixo-colide-no-meio"),
    ],
)
def test_TDD2_sufixo_de_dedup_nao_colide_com_nome_ja_existente(
    cabecalho: list,
) -> None:
    """O sufixo gerado não pode coincidir com nenhum outro nome do cabeçalho.

    As três ordens importam: o nome que colide com o sufixo pode aparecer
    depois, antes ou no meio das repetições, e cada ordem exercita um caminho
    diferente da busca por um nome livre.
    """
    cliente = ClientePPA(ano_ppa=ANO)

    nomes = cliente._nomes_colunas(cabecalho)

    assert len(set(nomes)) == len(nomes), nomes


def test_TDD2_nenhuma_coluna_do_csv_e_perdida(tmp_path: Path) -> None:
    """Três colunas no CSV têm de render três colunas no registro."""
    cliente = _cliente(tmp_path, _csv("Ano;Ano;Ano 2", "x;y;z"))

    registro = _negocio(_ler(cliente)[0])

    assert len(registro) == 3
    assert "y" in registro.values()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-3: zip(nomes, linha) para no mais curto dos dois. Uma linha com "
        "mais campos que o cabeçalho tem o excedente descartado em silêncio, "
        "em vez de erro. Encontrado pelo ramo D10, que não tem nenhuma "
        "decisão validando a aridade da linha."
    ),
)
def test_DEF3_linha_mais_longa_que_o_cabecalho_e_truncada(tmp_path: Path) -> None:
    """Campo a mais na linha: deveria falhar, mas é descartado."""
    cliente = _cliente(tmp_path, _csv("A;B", "1;2;3"))

    with pytest.raises(ValueError):
        _ler(cliente)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-3 (variante): uma linha com menos campos que o cabeçalho rende um "
        "registro parcial, e como _id_hash percorre só as chaves presentes, "
        "esse registro recebe um hash diferente do mesmo registro com a coluna "
        "final vazia. A reingestão deixa de ser idempotente."
    ),
)
def test_DEF3_linha_mais_curta_gera_registro_parcial(tmp_path: Path) -> None:
    """Linha truncada e linha completa com campo vazio deveriam coincidir."""
    curta = _cliente(tmp_path / "curta", _csv("A;B;C", "1;2"))
    completa = _cliente(tmp_path / "completa", _csv("A;B;C", "1;2;"))

    assert _ler(curta)[0] == _ler(completa)[0]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-4: normalizar_coluna promete no docstring um identificador "
        "'válido no Postgres', mas um cabeçalho cujo primeiro caractere "
        "alfanumérico é dígito gera slug começando por dígito. O DDL de "
        "cliente_postgres.py:171 interpola a coluna sem quotar "
        "(f'{column} TEXT'), então o CREATE TABLE fica sintaticamente "
        "inválido. Encontrado pela AVL do cabeçalho contra o contrato."
    ),
)
@pytest.mark.parametrize("cabecalho", ["1 ano PPA", "2024", "1º ano"])
def test_DEF4_slug_pode_comecar_por_digito(cabecalho: str) -> None:
    """Identificador sem quote no Postgres tem de começar por letra ou ``_``."""
    slug = ClientePPA.normalizar_coluna(cabecalho)

    assert slug[0].isalpha() or slug[0] == "_", slug


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-5: um CSV cuja primeira linha está em branco rende cabecalho == "
        "[], o laço de _nomes_colunas não itera e todo registro sai sem coluna "
        "de negócio alguma. Como o hash passa a ser md5('ano_ppa=<ano>'), "
        "todos os registros do arquivo recebem o MESMO id_hash e o dedup do "
        "DAG reduz o lote a uma única linha. Alcançável só pelo ramo falso de "
        "D11, que nenhum caso derivado da especificação constrói."
    ),
)
def test_DEF5_cabecalho_vazio_colapsa_todos_os_registros(tmp_path: Path) -> None:
    """Linha em branco inicial: 3 linhas de dados, 1 id_hash."""
    cliente = _cliente(tmp_path, _csv("", "A;B", "1;2", "3;4"))

    registros = _ler(cliente)

    assert len({r["id_hash"] for r in registros}) == len(registros)


# ===========================================================================
# Complemento: ``baixar_zip``
# ---------------------------------------------------------------------------
# Fora do método em escopo, mas é o único trecho do módulo que ficava sem
# cobertura. Incluído para fechar cliente_ppa.py em 100% de linhas e ramos.
# ===========================================================================
def test_CP9a_baixar_zip_sem_url_levanta_valueerror() -> None:
    """Instância sem URL (ano fora do mapa de zips) não pode baixar nada."""
    cliente = ClientePPA(ano_ppa=ANO)

    with pytest.raises(ValueError, match=f"URL não informada para o ano {ANO}"):
        cliente.baixar_zip()


def test_CP9b_baixar_zip_grava_os_chunks_e_devolve_o_caminho(
    tmp_path: Path,
) -> None:
    """Caminho feliz: o corpo é gravado em streaming, sem carregar na memória."""
    cliente = ClientePPA(ano_ppa=ANO, url="https://exemplo.gov.br/ppa.zip")
    cliente.zip_path = str(tmp_path / "ppa.zip")
    resposta = Mock()
    resposta.iter_content.return_value = [b"PK\x03\x04", b"resto"]

    with patch("cliente_ppa.requests.get", return_value=resposta) as get:
        retorno = cliente.baixar_zip()

    assert retorno == cliente.zip_path
    assert Path(cliente.zip_path).read_bytes() == b"PK\x03\x04resto"
    assert get.call_args.kwargs["stream"] is True


def test_CP9c_baixar_zip_propaga_erro_http(tmp_path: Path) -> None:
    """Falha na fonte não pode virar um zip truncado em disco."""
    cliente = ClientePPA(ano_ppa=ANO, url="https://exemplo.gov.br/ppa.zip")
    cliente.zip_path = str(tmp_path / "ppa.zip")
    resposta = Mock()
    resposta.raise_for_status.side_effect = requests.HTTPError("404")

    with patch("cliente_ppa.requests.get", return_value=resposta):
        with pytest.raises(requests.HTTPError):
            cliente.baixar_zip()

    assert not Path(cliente.zip_path).exists()


# ===========================================================================
# Rastreabilidade
# ===========================================================================
def test_rastreabilidade_funcionalidade_ponta_a_ponta(tmp_path: Path) -> None:
    """Um CSV com todas as características reais da fonte do PPA/SIOP.

    Fecha a rastreabilidade entre a funcionalidade (ingestão do PPA, #477) e
    os testes: zip aninhado, latin-1, cabeçalho humano com acento, ``;`` final,
    linha em branco de rodapé e os dois campos acrescentados pelo cliente.
    """
    cliente = _cliente(
        tmp_path,
        _csv(
            "Código;Objetivo Específico;Valor Global (R$);",
            "0001;Reduzir a desigualdade regional;1.000,00;",
            "0002;Ampliar a cobertura do Norte;2.500,50;",
            ";;;",
        ),
        nome_no_zip=f"PPA_{ANO}/dados/tabela_{ANO}.csv",
    )

    registros = _ler(
        cliente, colunas_esperadas=["codigo", "objetivo_especifico", "valor_global_r"]
    )

    assert [_negocio(r) for r in registros] == [
        {
            "codigo": "0001",
            "objetivo_especifico": "Reduzir a desigualdade regional",
            "valor_global_r": "1.000,00",
        },
        {
            "codigo": "0002",
            "objetivo_especifico": "Ampliar a cobertura do Norte",
            "valor_global_r": "2.500,50",
        },
    ]
    assert all(r["ano_ppa"] == ANO for r in registros)
    assert len({r["id_hash"] for r in registros}) == 2
