from typing import Dict, Any
from requests import Session
import requests

from zeep import Transport, Client


class ClienteSiape(object):

    BEARER_ENDPOINT = (
        "***REMOVED***"
    )
    SOAP_ENDPOINT = "https://apigateway.conectagov.estaleiro.serpro.gov.br/api-consulta-siape/v1/consulta-siape"

    def __init__(self, oauth_username: str, oauth_password: str) -> None:
        token = ClienteSiape._get_token(oauth_username, oauth_password)
        headers = ClienteSiape._get_headers(token)
        session = Session()
        session.headers.update(headers)
        transport = Transport(session=session)
        self.base_url = ClienteSiape.SOAP_ENDPOINT
        self.client = Client(ClienteSiape.SOAP_ENDPOINT, transport=transport)

    @staticmethod
    def _get_token(oauth_username: str, oauth_password: str) -> str:
        """
        Gets the token for the client.

        Args:
            oauth_username (str): The OAuth username.
            oauth_password (str): The OAuth password.

        Returns:
            str: The token.
        """
        auth_response = requests.get(
            ClienteSiape.BEARER_ENDPOINT,
            auth=(oauth_username, oauth_password),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        auth_json = auth_response.json()
        return str(auth_json.get("access_token", ""))

    @staticmethod
    def _get_headers(token: str) -> Dict[str, str]:
        """
        Builds the headers for the client.

        Args:
            token (str): The OAuth token.

        Returns:
            Dict[str, str]: The headers.
        """
        return {"Authorization": f"Bearer {token}"}

    def method(self, method_name: str) -> Any:
        """
        Applies the method to the client.

        Args:
            method_name (str): The method name.

        Returns:
            Any: The response.
        """
        try:
            response = getattr(self.client.service, method_name)
            return response
        except Exception as e:
            raise Exception(f"Error making SOAP request: {str(e)}")
