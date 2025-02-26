from unittest.mock import patch, MagicMock
from airflow_lappis.plugins.cliente_postgres import ClientPostgresDB


@patch("airflow_lappis.plugins.cliente_postgres.psycopg2.connect")
def test_insert_data(mock_connect):
    # Criando uma instância mock do banco de dados
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Configurando o mock para retornar os objetos corretos
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Configurando encoding da conexão para evitar KeyError
    mock_conn.encoding = "UTF8"
    mock_cursor.connection.encoding = "UTF8"

    # Criando a instância do ClientPostgresDB com um conn_str fictício
    db_client = ClientPostgresDB(conn_str="fake_connection_string")

    # Dados de entrada para o teste
    data = [{"id": 1, "name": "John Doe"}, {"id": 2, "name": "Jane Doe"}]
    table_name = "users"
    schema = "public"
    conflict_fields = ["id"]
    primary_key = ["id"]

    # Chamando o método a ser testado
    with patch("psycopg2.extras.execute_values") as mock_execute_values:
        db_client.insert_data(data, table_name, conflict_fields, primary_key, schema)

        # Verificando se a query foi construída corretamente
        expected_sql = (
            f"INSERT INTO {schema}.{table_name} (id, name) VALUES %s "
            "ON CONFLICT (id) DO UPDATE SET id = EXCLUDED.id, name = EXCLUDED.name"
        )

        # Verificando se execute_values foi chamado corretamente
        mock_execute_values.assert_called_once_with(
            mock_cursor, expected_sql, [(1, "John Doe"), (2, "Jane Doe")]
        )

    # Garantir que commit foi chamado
    mock_conn.commit.assert_called_once()
