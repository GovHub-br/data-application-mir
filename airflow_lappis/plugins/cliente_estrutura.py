import http
from typing import Optional

from cliente_base import ClienteBase


class ClienteEstrutura(ClienteBase):

    BASE_URL = "https://estruturaorganizacional.dados.gov.br/doc"

    def __init__(self) -> None:
        super().__init__(base_url=ClienteEstrutura.BASE_URL)

    def get_estrutura_organizacional_resumida(
        self,
        codigo_poder: Optional[str] = None,
        codigo_esfera: Optional[str] = None,
        codigo_unidade: Optional[str] = None,
    ) -> Optional[list]:
        """
        Consultar Estrutura Organizacional Resumida.

        Args:
            codigo_poder (Optional[str]): código do poder
            codigo_esfera (Optional[str]): código da esfera
            codigo_unidade (Optional[str]): código da unidade

        Returns:
            dict: Estrutura Organizacional Resumida.
        """
        endpoint = "/estrutura-organizacional/resumida"
        params = {}
        if codigo_poder:
            params["codigoPoder"] = codigo_poder
        if codigo_esfera:
            params["codigoEsfera"] = codigo_esfera
        if codigo_unidade:
            params["codigoUnidade"] = codigo_unidade

        status, data = self.request(http.HTTPMethod.GET, endpoint, params=params)
        return (
            data.get("unidades")
            if status == http.HTTPStatus.OK and type(data) is dict and "unidades" in data
            else None
        )
