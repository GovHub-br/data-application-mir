from unittest.mock import MagicMock, patch

import pytest

from cliente_postgres import ClientPostgresDB


def _mock_connect(columns: list[str], rows: list[tuple]) -> MagicMock:
    cursor = MagicMock()
    cursor.description = [(col,) for col in columns]
    cursor.fetchall.return_value = rows
    cursor.__enter__.return_value = cursor

    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_fetch_table_retorna_lista_de_dicts_com_nome_das_colunas() -> None:
    conn = _mock_connect(["id_plano_acao", "empenhado"], [(1, 10.5), (2, None)])

    with patch("cliente_postgres.psycopg2.connect", return_value=conn):
        linhas = ClientPostgresDB("dsn").fetch_table("siafi_dbt", "planos_acao_ted")

    assert linhas == [
        {"id_plano_acao": 1, "empenhado": 10.5},
        {"id_plano_acao": 2, "empenhado": None},
    ]
    conn.cursor.return_value.execute.assert_called_once_with(
        "SELECT * FROM siafi_dbt.planos_acao_ted"
    )
    conn.close.assert_called_once()


def test_fetch_table_tabela_vazia_retorna_lista_vazia() -> None:
    conn = _mock_connect(["id"], [])

    with patch("cliente_postgres.psycopg2.connect", return_value=conn):
        assert ClientPostgresDB("dsn").fetch_table("s", "t") == []


@pytest.mark.parametrize("schema, table", [("bad;drop", "t"), ("s", "t--x"), ("", "t")])
def test_fetch_table_rejeita_identificadores_invalidos(schema: str, table: str) -> None:
    with pytest.raises(ValueError):
        ClientPostgresDB("dsn").fetch_table(schema, table)
