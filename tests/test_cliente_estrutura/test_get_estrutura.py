import pytest
import http
from unittest.mock import patch, Mock
from http import HTTPStatus
from airflow_lappis.plugins.cliente_estrutura import ClienteEstrutura


@pytest.fixture
def cliente_estrutura():
    return ClienteEstrutura()


def test_get_estrutura_organizacional_resumida_success(cliente_estrutura):
    # Configura o mock para retornar uma resposta bem-sucedida
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"unidades": [{"id": 1, "nome": "Unidade 1"}]}

    with patch(
        "airflow_lappis.plugins.cliente_estrutura.ClienteBase.request",
        return_value=(HTTPStatus.OK, mock_response.json.return_value),
    ):
        # Chama o método get_estrutura_organizacional_resumida
        result = cliente_estrutura.get_estrutura_organizacional_resumida()

        # Verifica se o resultado é o esperado
        assert result == [{"id": 1, "nome": "Unidade 1"}]


def test_get_estrutura_organizacional_resumida_failure(cliente_estrutura):
    # Configura o mock para retornar uma resposta de falha
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.NOT_FOUND
    mock_response.json.return_value = None

    with patch(
        "airflow_lappis.plugins.cliente_estrutura.ClienteBase.request",
        return_value=(HTTPStatus.NOT_FOUND, None),
    ):
        # Chama o método get_estrutura_organizacional_resumida
        result = cliente_estrutura.get_estrutura_organizacional_resumida()

        # Verifica se o resultado é None (falha)
        assert result is None


def test_get_estrutura_organizacional_resumida_invalid_data(cliente_estrutura):
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {
        "id": 1,
        "nome": "Unidade 1",
    }  # Dados inválidos (não tem a chave "unidades")

    with patch(
        "airflow_lappis.plugins.cliente_estrutura.ClienteBase.request",
        return_value=(HTTPStatus.OK, mock_response.json.return_value),
    ):
        # Chama o método get_estrutura_organizacional_resumida
        result = cliente_estrutura.get_estrutura_organizacional_resumida()

        # Verifica se o resultado é None (dados inválidos)
        assert result is None


def test_get_estrutura_organizacional_resumida_with_params(cliente_estrutura):
    # Configura o mock para retornar uma resposta bem-sucedida
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"unidades": [{"id": 1, "nome": "Unidade 1"}]}

    with patch(
        "airflow_lappis.plugins.cliente_estrutura.ClienteBase.request",
        return_value=(HTTPStatus.OK, mock_response.json.return_value),
    ):
        # Chama o método get_estrutura_organizacional_resumida com parâmetros
        result = cliente_estrutura.get_estrutura_organizacional_resumida(
            codigo_poder="1", codigo_esfera="2", codigo_unidade="3"
        )

        # Verifica se o resultado é o esperado
        assert result == [{"id": 1, "nome": "Unidade 1"}]

        # Verifica se os parâmetros foram passados corretamente
        cliente_estrutura.request.assert_called_once_with(
            http.HTTPMethod.GET,
            "/estrutura-organizacional/resumida",
            params={"codigoPoder": "1", "codigoEsfera": "2", "codigoUnidade": "3"},
        )
