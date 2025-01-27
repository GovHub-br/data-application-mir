import json
import logging
from typing import Any
import requests
from httpx import HTTPStatusError

from .cliente_base import ClienteBase


class ClienteSiafi(ClienteBase):

    BEARER_ENDPOINT = "***REMOVED***"
    SIAFI_ENDPOINT = "https://gateway.apiserpro.serpro.gov.br/api-integra-siafi/api/v2"

    def __init__(
        self, bearer_key: str, bearer_secret: str, siafi_credential: str
    ) -> None:
        headers = ClienteSiafi._setup_headers(
            ClienteSiafi.BEARER_ENDPOINT, bearer_key, bearer_secret, siafi_credential
        )
        super().__init__(base_url=ClienteSiafi.SIAFI_ENDPOINT, headers=headers)

    @staticmethod
    def _get_token(url: str, consumer_key: str, consumer_secret: str) -> str:
        """
        Gets token from token endpoint.

        Args:
            url: Token endpoint.
            consumer_key: Consumer key.
            consumer_secret: Consumer secret.

        Returns:
            str: The token.
        """
        response = requests.post(
            url,
            data={"grant_type": "client_credentials"},
            auth=(consumer_key, consumer_secret),
        )
        data = response.json()
        return str(data.get("access_token", ""))

    @staticmethod
    def _setup_headers(
        bearer_endpoint: str, bearer_key: str, bearer_secret: str, siafi_credential: str
    ) -> dict:
        """
        Setups the headers for the client.

        Args:
            bearer_endpoint: Bearer endpoint.
            bearer_key: Bearer key.
            bearer_secret: Bearer secret.
            siafi_credential: Credencial SIAFI.

        Returns:
            dict: The headers.
        """
        bearer_token = ClienteSiafi._get_token(
            url=bearer_endpoint, consumer_key=bearer_key, consumer_secret=bearer_secret
        )
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "x-credencial": siafi_credential,
        }
        return headers

    def get(self, endpoint: str) -> Any:
        """
        Makes a GET request to the siafi endpoint.

        Args:
            endpoint: The endpoint.

        Returns:
            Any: The response data.
        """

        try:
            response = self.client.get(url=endpoint)
            response.raise_for_status()
            data = response.json()
            return data
        except HTTPStatusError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
        except json.decoder.JSONDecodeError:
            logging.warning(f"Could not decode response from {endpoint}")
        return None
