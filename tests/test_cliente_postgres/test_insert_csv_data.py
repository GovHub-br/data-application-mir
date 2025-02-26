from unittest.mock import patch, MagicMock
from airflow_lappis.plugins.cliente_postgres import ClientPostgresDB


@patch("airflow_lappis.plugins.cliente_postgres.psycopg2.connect")
def test_insert_csv_data(mock_connect):
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
    csv_data = "id,name\n1,John Doe\n2,Jane Doe"
    table_name = "users"
    schema = "public"

    # Chamando o método a ser testado
    with (
        patch.object(db_client, "drop_table_if_exists") as mock_drop_table_if_exists,
        patch.object(db_client, "insert_data") as mock_insert_data,
    ):

        db_client.insert_csv_data(csv_data, table_name, schema)

        # Verificando se drop_table_if_exists foi chamado corretamente
        mock_drop_table_if_exists.assert_called_once_with(table_name, schema)

        # Verificando se insert_data foi chamado corretamente
        expected_data = [{"id": 1, "name": "John Doe"}, {"id": 2, "name": "Jane Doe"}]
        mock_insert_data.assert_called_once_with(
            expected_data, table_name, primary_key=None, schema=schema
        )
