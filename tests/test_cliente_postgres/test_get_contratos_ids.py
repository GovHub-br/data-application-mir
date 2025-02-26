from unittest.mock import patch, MagicMock
from airflow_lappis.plugins.cliente_postgres import ClientPostgresDB


@patch("airflow_lappis.plugins.cliente_postgres.psycopg2.connect")
def test_get_contratos_ids(mock_connect):
    # Criando uma instância mock do banco de dados
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Configurando o mock para retornar os objetos corretos
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Definindo valores simulados que o banco retornaria
    mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]

    # Criando a instância do ClientPostgresDB com um conn_str fictício
    db_client = ClientPostgresDB(conn_str="fake_connection_string")

    # Chamando o método a ser testado
    contratos_ids = db_client.get_contratos_ids()

    # Verificando se a query foi executada corretamente
    mock_cursor.execute.assert_called_once_with("SELECT id FROM raw.contratos")

    # Verificando se o retorno do método está correto
    assert contratos_ids == [1, 2, 3]
