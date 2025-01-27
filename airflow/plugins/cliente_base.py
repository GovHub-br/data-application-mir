import http
import logging
import time
from http import HTTPStatus
from typing import Tuple, Optional, Any

import httpx


class ClienteBase(object):

    DEFAULT_MAX_RETRIES = 5
    DEFAULT_SLEEP_SECONDS = 1
    DEFAULT_TIMEOUT = 30

    def __init__(self, base_url: str, **kwargs: Optional[dict]) -> None:
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, **kwargs)

    def request(
        self, method: http.HTTPMethod, path: str, **kwargs: Any
    ) -> Tuple[http.HTTPStatus, Optional[dict | list]]:
        """
        Faz uma requisição HTTP em até DEFAULT_MAX_RETRIES+1 tentativas.

        Args:
            method (HTTPMethod): HTTP Method.
            path (str): URL path.

        Returns:
            Tuple[http.HTTPStatus, dict]: status e resposta da requisição HTTP.
        """
        kwargs["timeout"] = kwargs.get("timeout", self.DEFAULT_TIMEOUT)
        response = None

        for attempt in range(self.DEFAULT_MAX_RETRIES):
            try:
                response = self.client.request(method, path, **kwargs)
                response.raise_for_status()
                return HTTPStatus(response.status_code), response.json()
            except httpx.HTTPError as e:
                if attempt < self.DEFAULT_MAX_RETRIES:
                    status = response.status_code if response else "Unknown"
                    logging.warning(f"API falhou com status {status}")
                    time.sleep(attempt**2 * self.DEFAULT_SLEEP_SECONDS)
                else:
                    raise Exception(
                        "API falhou após o número máximo de tentativas!"
                    ) from e

        return HTTPStatus.INTERNAL_SERVER_ERROR, None
