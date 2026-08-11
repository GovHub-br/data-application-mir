import logging
import math
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


class ClienteOneDrive:
    """Cliente para autenticação client-credentials no Azure AD e upload de
    arquivos para o OneDrive de um usuário via Microsoft Graph API."""

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    SIMPLE_UPLOAD_LIMIT_BYTES = 4 * 1024 * 1024
    UPLOAD_CHUNK_SIZE_BYTES = 60 * 1024 * 1024

    def __init__(self, client_id: str, client_secret: str, tenant_id: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id

    def _get_access_token(self) -> str:
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        logging.info("[cliente_onedrive.py] Token de acesso obtido com sucesso")
        return response.json()["access_token"]

    @staticmethod
    def _item_path(folder_path: str, file_name: str) -> str:
        clean_folder = (folder_path or "").strip("/")
        path = f"{clean_folder}/{file_name}" if clean_folder else file_name
        return quote(path, safe="/")

    def upload_file(
        self,
        user_id: str,
        folder_path: str,
        file_name: str,
        content: bytes,
    ) -> Dict[str, Any]:
        """Envia um arquivo para o OneDrive do usuário informado.

        Usa upload simples para arquivos até 4MB e upload em sessão
        (chunks) para arquivos maiores, conforme exigido pela Microsoft
        Graph API (https://learn.microsoft.com/graph/api/driveitem-put-content).
        """
        token = self._get_access_token()
        item_path = self._item_path(folder_path, file_name)

        if len(content) <= self.SIMPLE_UPLOAD_LIMIT_BYTES:
            return self._upload_simple(token, user_id, item_path, content)
        return self._upload_in_session(token, user_id, item_path, content)

    def _upload_simple(
        self, token: str, user_id: str, item_path: str, content: bytes
    ) -> Dict[str, Any]:
        url = f"{self.GRAPH_BASE_URL}/users/{user_id}/drive/root:/{item_path}:/content"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
        }
        response = requests.put(url, headers=headers, data=content, timeout=60)
        response.raise_for_status()
        logging.info(f"[cliente_onedrive.py] Upload simples concluído: {item_path}")
        return response.json()

    def _upload_in_session(
        self, token: str, user_id: str, item_path: str, content: bytes
    ) -> Dict[str, Any]:
        session_url = (
            f"{self.GRAPH_BASE_URL}/users/{user_id}/drive/root:/{item_path}:"
            "/createUploadSession"
        )
        headers = {"Authorization": f"Bearer {token}"}
        body = {"item": {"@microsoft.graph.conflictBehavior": "replace"}}
        session_response = requests.post(
            session_url, headers=headers, json=body, timeout=30
        )
        session_response.raise_for_status()
        upload_url = session_response.json()["uploadUrl"]

        total_size = len(content)
        chunk_size = self.UPLOAD_CHUNK_SIZE_BYTES
        last_response: Optional[requests.Response] = None

        for start in range(0, total_size, chunk_size):
            end = min(start + chunk_size, total_size)
            chunk = content[start:end]
            chunk_headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end - 1}/{total_size}",
            }
            last_response = requests.put(
                upload_url, headers=chunk_headers, data=chunk, timeout=120
            )
            last_response.raise_for_status()

        logging.info(
            f"[cliente_onedrive.py] Upload em sessão concluído: {item_path} "
            f"({total_size} bytes em {math.ceil(total_size / chunk_size)} partes)"
        )
        return last_response.json() if last_response else {}
