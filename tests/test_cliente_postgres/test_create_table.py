from unittest.mock import patch, MagicMock
from airflow_lappis.plugins.cliente_postgres import ClientPostgresDB


@patch("psycopg2.connect")  # Mockando a conexão com o banco
def test_create_table_if_not_exists(mock_connect):
    # Criamos um mock para o cursor do banco
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Dados fictícios para o teste
    sample_data = {"id": 1, "name": "Alice"}
    table_name = "users"
    primary_key = ["id"]
    schema = "public"

    # Criamos a instância da classe
    db = ClientPostgresDB("fake_connection_string")

    # Chamamos o método que queremos testar
    db.create_table_if_not_exists(sample_data, table_name, primary_key, schema)

    # Verificamos se os métodos corretos foram chamados no banco
    mock_cursor.execute.assert_any_call(f"CREATE SCHEMA IF NOT EXISTS {schema};")
    create_table_query = (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table_name} ("
        f"id TEXT, name TEXT, PRIMARY KEY (id));"
    )
    mock_cursor.execute.assert_any_call(create_table_query)
