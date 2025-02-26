from unittest.mock import patch, MagicMock
from airflow_lappis.plugins.cliente_postgres import ClientPostgresDB


@patch("airflow_lappis.plugins.cliente_postgres.psycopg2.connect")
def test_drop_table_if_exists(mock_connect):
    # Criando uma instância mock do banco de dados
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Configurando o mock para retornar os objetos corretos
    mock_connect.return_value = mock_conn  # Simula a conexão
    mock_conn.cursor.return_value = mock_cursor  # Simula o cursor

    # Criando a instância do ClientPostgresDB com um conn_str fictício
    db_client = ClientPostgresDB(conn_str="fake_connection_string")

    # Definindo os parâmetros para o teste
    schema = "raw"
    table_name = "test_table"

    # Chamando o método a ser testado
    db_client.drop_table_if_exists(table_name, schema)

    # Verificando se a query foi executada corretamente
    mock_cursor.execute.assert_called_once_with(
        f"DROP TABLE IF EXISTS {schema}.{table_name};"
    )

    # Verificando se o commit foi chamado
    mock_conn.commit.assert_called_once()

    # Verificando se o cursor e a conexão foram fechados
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("airflow_lappis.plugins.cliente_postgres.psycopg2.connect")
def test_drop_table_if_exists_error(mock_connect):
    # Criando uma instância mock do banco de dados
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Configurando o mock para simular um erro ao executar a query
    mock_connect.return_value = mock_conn  # Simula a conexão
    mock_conn.cursor.return_value = mock_cursor  # Simula o cursor
    mock_cursor.execute.side_effect = Exception(
        "Erro simulado"
    )  # Simula um erro ao executar a query

    # Criando a instância do ClientPostgresDB com um conn_str fictício
    db_client = ClientPostgresDB(conn_str="fake_connection_string")

    # Definindo os parâmetros para o teste
    schema = "raw"
    table_name = "test_table"

    # Chamando o método a ser testado
    db_client.drop_table_if_exists(table_name, schema)

    # Verificando se a query foi executada corretamente
    mock_cursor.execute.assert_called_once_with(
        f"DROP TABLE IF EXISTS {schema}.{table_name};"
    )

    # Verificando se o commit NÃO foi chamado (já que houve um erro)
    mock_conn.commit.assert_not_called()

    # Verificando se o cursor e a conexão foram fechados
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()
