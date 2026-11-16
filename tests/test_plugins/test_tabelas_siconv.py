"""Configuração das tabelas do SICONV ingeridas pela siconv_ingestao_dag."""

import pytest

from tabelas_siconv import TABELAS_SICONV


@pytest.mark.parametrize("tabela", TABELAS_SICONV, ids=lambda t: t["nome_tabela"])
def test_toda_tabela_e_substituida_a_cada_carga(tabela):
    # Com upsert, a linha que sai da fonte (proposta excluída, meta refeita com id
    # novo) fica para sempre na bronze.
    assert tabela["truncate_before_insert"] is True


@pytest.mark.parametrize("tabela", TABELAS_SICONV, ids=lambda t: t["nome_tabela"])
def test_chave_esta_entre_as_colunas_lidas(tabela):
    colunas = {c.lower() for c in tabela["colunas"]}
    assert set(tabela["primary_key"]) <= colunas
    assert set(tabela["conflict_fields"]) <= colunas


def test_emenda_so_entra_com_proposta_do_mir():
    # As linhas sem ID_PROPOSTA repetem a chave e derrubariam o ON CONFLICT do lote.
    emenda = next(t for t in TABELAS_SICONV if t["nome_tabela"] == "emenda")

    assert "67000" in emenda["filtro_ids_sql"]
    assert emenda["primary_key"] == ["id_proposta", "nr_emenda", "cod_programa_emenda"]
