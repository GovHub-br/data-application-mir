import pytest
from unittest.mock import patch, Mock
from http import HTTPStatus
import httpx
from airflow_lappis.plugins.cliente_base import ClienteBase


@pytest.fixture
def cliente_base():
    return ClienteBase(base_url="http://example.com")


def test_request_success(cliente_base):
    # Configura o mock para retornar uma resposta bem-sucedida
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"key": "value"}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client.request", return_value=mock_response):
        # Chama o método request
        status, response = cliente_base.request("GET", "/test")

        # Verifica se o status e a resposta são os esperados
        assert status == HTTPStatus.OK
        assert response == {"key": "value"}


def test_request_failure(cliente_base):
    # Configura o mock para simular uma exceção HTTPError
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_response.raise_for_status.side_effect = httpx.HTTPError("Bad Request")

    with patch("httpx.Client.request", return_value=mock_response):
        # Chama o método request e verifica se a exceção é levantada após as tentativas
        with pytest.raises(
            Exception, match="API failed after the maximum number of attempts!"
        ):
            cliente_base.request("GET", "/test")
