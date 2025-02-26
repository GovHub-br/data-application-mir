import pytest
from unittest.mock import patch, Mock
from http import HTTPStatus
from airflow_lappis.plugins.cliente_contratos import ClienteContratos


@pytest.fixture
def cliente_contratos():
    return ClienteContratos()


def test_get_contratos_inativos_by_ug_success(cliente_contratos):
    # Configura o mock para retornar uma resposta bem-sucedida
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = [{"id": 1, "ug_code": "12345", "status": "inativo"}]

    with patch(
        "airflow_lappis.plugins.cliente_contratos.ClienteBase.request",
        return_value=(HTTPStatus.OK, mock_response.json.return_value),
    ):
        # Chama o método get_contratos_inativos_by_ug
        result = cliente_contratos.get_contratos_inativos_by_ug("12345")

        # Verifica se o resultado é o esperado
        assert result == [{"id": 1, "ug_code": "12345", "status": "inativo"}]


def test_get_contratos_inativos_by_ug_failure(cliente_contratos):
    # Configura o mock para retornar uma resposta de falha
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.NOT_FOUND
    mock_response.json.return_value = None

    with patch(
        "airflow_lappis.plugins.cliente_contratos.ClienteBase.request",
        return_value=(HTTPStatus.NOT_FOUND, None),
    ):
        # Chama o método get_contratos_inativos_by_ug
        result = cliente_contratos.get_contratos_inativos_by_ug("12345")

        # Verifica se o resultado é None (falha)
        assert result is None


def test_get_contratos_inativos_by_ug_invalid_data(cliente_contratos):
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {
        "id": 1,
        "ug_code": "12345",
    }  # Dados inválidos (não é uma lista)

    with patch(
        "airflow_lappis.plugins.cliente_contratos.ClienteBase.request",
        return_value=(HTTPStatus.OK, mock_response.json.return_value),
    ):
        # Chama o método get_contratos_inativos_by_ug
        result = cliente_contratos.get_contratos_inativos_by_ug("12345")

        # Verifica se o resultado é None (dados inválidos)
        assert result is None
