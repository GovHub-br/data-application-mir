"""Configuração das tabelas do SICONV ingeridas pela siconv_ingestao_dag."""

import pytest

from tabelas_siconv import TABELAS_SICONV


@pytest.mark.parametrize("tabela", TABELAS_SICONV, ids=lambda t: t["nome_tabela"])
def test_toda_tabela_e_substituida_a_cada_carga(tabela):
    # Com upsert, a linha que sai da fonte (proposta excluída, meta refeita com id
    # novo) fica para sempre na bronze.
    assert tabela["truncate_before_insert"] is True
