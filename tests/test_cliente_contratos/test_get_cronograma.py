import pytest
from unittest.mock import patch, Mock
from http import HTTPStatus
from airflow_lappis.plugins.cliente_contratos import ClienteContratos


@pytest.fixture
def cliente_contratos():
    return ClienteContratos()


def test_get_cronograma_by_contrato_id_success(cliente_contratos):
    # Mockando a resposta esperada
    mock_response = Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = [
        {"id": 1, "contrato_id": "98765", "etapa": "Fundação"},
        {"id": 2, "contrato_id": "98765", "etapa": "Estrutura"},
    ]

    with patch(
        "airflow_lappis.plugins.cliente_contratos.ClienteBase.request",
        return_value=(HTTPStatus.OK, mock_response.json.return_value),
    ):
        result = cliente_contratos.get_cronograma_by_contrato_id("98765")
        assert result == [
            {"id": 1, "contrato_id": "98765", "etapa": "Fundação"},
            {"id": 2, "contrato_id": "98765", "etapa": "Estrutura"},
        ]


def test_get_cronograma_by_contrato_id_failure(cliente_contratos):
    # Mockando uma resposta de falha
    with patch(
        "airflow_lappis.plugins.cliente_contratos.ClienteBase.request",
        return_value=(HTTPStatus.NOT_FOUND, None),
    ):
        result = cliente_contratos.get_cronograma_by_contrato_id("98765")
        assert result is None


def test_get_cronograma_by_contrato_id_invalid_data(cliente_contratos):
    # Mockando uma resposta com dados inválidos (não é uma lista)
    with patch(
        "airflow_lappis.plugins.cliente_contratos.ClienteBase.request",
        return_value=(HTTPStatus.OK, {"id": 1, "contrato_id": "98765"}),
    ):
        result = cliente_contratos.get_cronograma_by_contrato_id("98765")
        assert result is None
