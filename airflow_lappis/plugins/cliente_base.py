import logging
import time
import httpx
from typing import Any, Optional, Tuple
from http import HTTPStatus


class ClienteBase:
    DEFAULT_TIMEOUT = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_SLEEP_SECONDS = 2
    # Erros 4xx que ainda valem nova tentativa (timeout e rate limit).
    RETRYABLE_CLIENT_ERRORS = frozenset(
        {HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.TOO_MANY_REQUESTS}
    )

    def __init__(self, base_url: str, headers: Optional[dict] = None) -> None:
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, headers=headers)
        logging.info(
            f"[cliente_base.py] Initialized ClienteBase with base_url: {base_url}"
        )

    def request(
        self, method: str, path: str, **kwargs: Any
    ) -> Tuple[HTTPStatus, Optional[dict | list]]:
        """
        Faz uma requisição HTTP em até DEFAULT_MAX_RETRIES+1 tentativas.

        Args:
            method (str): HTTP Method.
            path (str): URL path.

        Returns:
            Tuple[HTTPStatus, dict]: status e resposta da requisição HTTP.
        """
        kwargs["timeout"] = kwargs.get("timeout", self.DEFAULT_TIMEOUT)

        for attempt in range(self.DEFAULT_MAX_RETRIES + 1):
            try:
                logging.info(
                    f"[cliente_base.py] Attempt {attempt + 1} for {method} "
                    f"{self.base_url}{path} with kwargs: {kwargs}"
                )
                response = self.client.request(method, path, **kwargs)
                response.raise_for_status()
                logging.info(
                    f"[cliente_base.py] Request successful with status "
                    f"{response.status_code}"
                )
                return HTTPStatus(response.status_code), response.json()
            except httpx.HTTPError as e:
                status = self._status_do_erro(e)
                if not self._deve_repetir(e):
                    raise Exception(f"API returned client error {status}") from e
                logging.warning(
                    f"[cliente_base.py] API failed with status {status} on "
                    f"attempt {attempt + 1}. Error: {str(e)}"
                )
                if attempt < self.DEFAULT_MAX_RETRIES:
                    time.sleep(attempt**2 * self.DEFAULT_SLEEP_SECONDS)
                else:
                    logging.error(
                        f"[cliente_base.py] API failed after "
                        f"{attempt + 1} attempts. Error: {str(e)}"
                    )
                    raise Exception(
                        "API failed after the maximum number of attempts!"
                    ) from e

        return HTTPStatus.INTERNAL_SERVER_ERROR, None

    @staticmethod
    def _status_do_erro(erro: httpx.HTTPError) -> int | str:
        """Status da tentativa que falhou ("Unknown" em erros de rede)."""
        if isinstance(erro, httpx.HTTPStatusError):
            return erro.response.status_code
        return "Unknown"

    @classmethod
    def _deve_repetir(cls, erro: httpx.HTTPError) -> bool:
        """
        Indica se vale nova tentativa. Erros 4xx são definitivos (repetir
        não muda o resultado), exceto 408 e 429; erros de rede, 3xx e 5xx
        são considerados transitórios.
        """
        if not isinstance(erro, httpx.HTTPStatusError):
            return True
        code = erro.response.status_code
        erro_cliente = 400 <= code <= 499
        return not (erro_cliente and code not in cls.RETRYABLE_CLIENT_ERRORS)
