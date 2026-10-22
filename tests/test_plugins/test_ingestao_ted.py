from unittest.mock import Mock

import pytest

from ingestao_ted import ENDPOINTS_TED, EndpointTed, ingerir_endpoint

DT = "2026-10-22T03:00:00"

META = EndpointTed(
    tabela_api="plano_acao_meta",
    coluna_filtro="id_plano_acao",
    tabela_ids="planos_acao",
    coluna_ids="id_plano_acao",
    tabela_destino="planos_acao_meta",
    ordem="id_meta",
)
EVENTO = EndpointTed(
    tabela_api="evento",
    coluna_filtro="id_nota",
    tabela_ids="notas_de_credito",
    coluna_ids="id_nota",
    tabela_destino="eventos_nota_credito",
    ordem="id_nota,cd_evento",
)


def _db(ids: list) -> Mock:
    db = Mock()
    db.execute_query.return_value = [(i,) for i in ids]
    return db


def test_catalogo_cobre_os_nove_endpoints_na_ordem_certa() -> None:
    tabelas = [e.tabela_api for e in ENDPOINTS_TED]
    assert sorted(tabelas) == sorted(
        [
            "plano_acao_meta",
            "plano_acao_etapa",
            "termo_execucao",
            "plano_acao_analise",
            "plano_acao_parecer",
            "evento",
            "trf",
            "programa_acao_orcamentaria",
            "programa_beneficiario",
        ]
    )
    assert tabelas.index("plano_acao_meta") < tabelas.index("plano_acao_etapa")


def test_ids_lidos_do_postgres_como_inteiros_distintos() -> None:
    db = _db(["64", "64.0", "65", None])
    api = Mock()
    api.get_por_ids.return_value = []

    ingerir_endpoint(api, db, META, DT)

    db.execute_query.assert_called_once_with(
        "select distinct id_plano_acao from transfere_gov.planos_acao"
    )
    api.get_por_ids.assert_called_once_with(
        "plano_acao_meta", "id_plano_acao", [64, 65], "id_meta"
    )


@pytest.mark.parametrize("endpoint", ENDPOINTS_TED, ids=lambda e: e.tabela_api)
def test_todo_endpoint_substitui_a_tabela_inteira(endpoint: EndpointTed) -> None:
    # get_por_ids devolve o retrato completo (ou None): linhas removidas na fonte
    # tambem saem do destino, inclusive nos endpoints com chave natural.
    db = _db([64])
    api = Mock()
    api.get_por_ids.return_value = [{"id": 1}]

    gravadas = ingerir_endpoint(api, db, endpoint, DT)

    assert gravadas == 1
    db.replace_rows.assert_called_once_with(
        [{"id": 1, "dt_ingest": DT}],
        endpoint.tabela_destino,
        delete_where="true",
        delete_params=(),
        schema="transfere_gov",
    )
    db.insert_data.assert_not_called()


def test_endpoint_nao_tem_mais_campo_chave() -> None:
    assert not hasattr(META, "chave")


def test_ordem_de_programa_beneficiario_inclui_nome() -> None:
    (beneficiario,) = [
        e for e in ENDPOINTS_TED if e.tabela_api == "programa_beneficiario"
    ]
    assert "tx_nome_beneficiario" in beneficiario.ordem.split(",")


def test_endpoint_sem_chave_natural_substitui_a_tabela_inteira() -> None:
    db = _db([7])
    api = Mock()
    api.get_por_ids.return_value = [{"id_nota": 7, "cd_evento": "x"}]

    ingerir_endpoint(api, db, EVENTO, DT)

    db.replace_rows.assert_called_once_with(
        [{"id_nota": 7, "cd_evento": "x", "dt_ingest": DT}],
        "eventos_nota_credito",
        delete_where="true",
        delete_params=(),
        schema="transfere_gov",
    )
    db.insert_data.assert_not_called()


def test_falha_da_api_nao_grava_e_levanta_erro() -> None:
    db = _db([7])
    api = Mock()
    api.get_por_ids.return_value = None

    with pytest.raises(RuntimeError, match="evento"):
        ingerir_endpoint(api, db, EVENTO, DT)

    db.insert_data.assert_not_called()
    db.replace_rows.assert_not_called()


def test_sem_ids_nao_chama_api() -> None:
    db = _db([])
    api = Mock()

    assert ingerir_endpoint(api, db, META, DT) == 0
    api.get_por_ids.assert_not_called()


def test_api_sem_linhas_nao_apaga_tabela() -> None:
    db = _db([7])
    api = Mock()
    api.get_por_ids.return_value = []

    assert ingerir_endpoint(api, db, EVENTO, DT) == 0
    db.replace_rows.assert_not_called()
