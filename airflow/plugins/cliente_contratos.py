import http

from cliente_base import ClienteBase


class ClienteContratos(ClienteBase):

    BASE_URL = "https://contratos.comprasnet.gov.br/api"
    BASE_HEADER = {"accept": "application/json"}

    def __init__(self) -> None:
        super().__init__(base_url=ClienteContratos.BASE_URL)

    def get_contratos_by_ug(self, ug_code: str) -> list | None:
        """
        Obter todos os contratos ativos de uma UG específica.

        Args:
            ug_code (str): UG code

        Returns:
            list: lista de contratos por ug
        """
        endpoint = f"/contrato/ug/{ug_code}"
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        return data if status == http.HTTPStatus.OK and type(data) is list else None

    def get_faturas_by_contrato_id(self, contrato_id: str) -> list | None:
        """
        Obter todas as faturas de um contrato específico.

        Args:
            contrato_id (str): id do contrato

        Returns:
            list: as faturas de um contrato específico.
        """
        endpoint = f"/contrato/{contrato_id}/faturas"
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        return data if status == http.HTTPStatus.OK and type(data) is list else None

    def get_empenhos_by_contrato_id(self, contrato_id: str) -> list | None:
        """
        Obter todos os empenhos de um contrato específico.

        Args:
            contrato_id (str): id do contrato

        Returns:
            list: os empenhos de um contrato específico.
        """
        endpoint = f"/contrato/{contrato_id}/empenhos"
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        return data if status == http.HTTPStatus.OK and type(data) is list else None

    def get_cronograma_by_contrato_id(self, contrato_id: str) -> list | None:
        """
        Obter todos os cronogramas de um contrato específico.

        Args:
            contrato_id (str): id do contrato

        Returns:
            list: cronogramas de um contrato específico.
        """
        endpoint = f"/contrato/{contrato_id}/cronograma"
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        return data if status == http.HTTPStatus.OK and type(data) is list else None
