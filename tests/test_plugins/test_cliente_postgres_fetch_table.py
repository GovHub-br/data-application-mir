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


def test_replace_rows_apaga_o_recorte_e_insere_na_mesma_transacao() -> None:
    conn = _mock_connect([], [])
    cursor = conn.cursor.return_value
    cursor.rowcount = 3
    dados = [{"nc": "A", "relatorio": "enviadas"}, {"nc": "A", "relatorio": "enviadas"}]

    with (
        patch("cliente_postgres.psycopg2.connect", return_value=conn),
        patch("cliente_postgres.psycopg2.extras.execute_values") as execute_values,
    ):
        apagadas = ClientPostgresDB("dsn").replace_rows(
            dados, "nc", "relatorio = %s", ("enviadas",), schema="siafi"
        )

    assert apagadas == 3
    cursor.execute.assert_any_call(
        "DELETE FROM siafi.nc WHERE relatorio = %s", ("enviadas",)
    )
    # linhas identicas sao inseridas as duas, sem ON CONFLICT
    sql, valores = execute_values.call_args.args[1:3]
    assert "ON CONFLICT" not in sql
    assert valores == [("A", "enviadas"), ("A", "enviadas")]
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_replace_rows_sem_dados_nao_conecta() -> None:
    with patch("cliente_postgres.psycopg2.connect") as connect:
        assert ClientPostgresDB("dsn").replace_rows([], "t", "1 = 1", ()) == 0
    connect.assert_not_called()


def test_replace_rows_rejeita_identificador_invalido() -> None:
    with pytest.raises(ValueError):
        ClientPostgresDB("dsn").replace_rows([{"a": 1}], "t; drop", "1 = 1", ())
