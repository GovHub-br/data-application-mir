import os
import logging
from zeep import Client
from zeep.transports import Transport
from zeep.wsse.username import UsernameToken
from requests import Session
from typing import Dict, Any, Optional

# Configuração do logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ClienteSiafi:
    def __init__(self) -> None:
        """
        Inicializa o cliente SIAFI com as configurações necessárias.
        """
        self.base_url = "https://servicos-siafi.tesouro.gov.br/siafi"
        self.cert_path = os.getenv("SIAFI_CERT_PATH")
        self.key_path = os.getenv("SIAFI_KEY_PATH")
        self.siafi_username = os.getenv("SIAFI_USERNAME")
        self.siafi_password = os.getenv("SIAFI_PASSWORD")

    def _criar_cliente_soap(self, ano: int, endpoint: str) -> Optional[Client]:
        """
        Cria e retorna um cliente SOAP para comunicação com o serviço SIAFI
        com a URL específica para o ano e endpoint informados.

        Args:
            ano (int): Ano para formar a URL do WSDL
            endpoint (str): Endpoint específico do serviço SIAFI

        Returns:
            Client: Cliente SOAP configurado ou None em caso de falha.
        """
        wsdl_url = f"{self.base_url}{ano}/{endpoint}?wsdl"
        logger.info(f"Criando cliente SOAP com URL: {wsdl_url}")

        if not isinstance(self.cert_path, str) or not isinstance(self.key_path, str):
            logger.error("Certificados SSL inválidos.")
            return None

        session = Session()
        session.verify = self.cert_path
        session.cert = (self.cert_path, self.key_path)

        transport = Transport(session=session)
        wsse = UsernameToken(self.siafi_username, self.siafi_password, use_digest=False)

        try:
            client = Client(wsdl_url, transport=transport, wsse=wsse)
            logger.info(
                f"Cliente SOAP para o ano {ano} e endpoint {endpoint} criado com sucesso."
            )
            return client
        except Exception as e:
            logger.error(
                f"Erro ao criar o cliente SOAP para ano {ano} e endpoint {endpoint}: {e}"
            )
            return None

    def consultar_programacao_financeira(
        self, ug_emitente: str, ano: int, num_lista: str
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta programações financeiras no SIAFI.

        Args:
            ug_emitente (str): UG emitente da programação financeira.
            ano (int): Ano da programação financeira.
            num_lista (str): Número do documento da programação financeira.

        Returns:
            dict: Resposta da consulta ou None em caso de falha.
        """
        endpoint = "services/pf/manterProgramacaoFinanceira"

        # Cria um cliente específico para o ano e endpoint da consulta
        client = self._criar_cliente_soap(ano, endpoint)
        if not client:
            logger.error(
                f"Não foi possível criar cliente SOAP ano {ano} e endpoint {endpoint}."
            )
            return None

        soap_headers = {
            "cabecalhoSIAFI": {
                "nomeSistemaSIAFI": f"SIAFI{str(ano)}",
                "ug": ug_emitente,
                "bilhetador": {"nonce": "nonce123456"},
            }
        }

        try:
            logger.info(
                f"Consultando Programação Financeira: UG {ug_emitente}, Ano {ano}, "
                f"Documento {num_lista}..."
            )
            response = client.service.pfDetalharProgramacaoFinanceira(
                _soapheaders=soap_headers,
                ano=ano,
                numeroDocumento=num_lista,
                codUgEmit=ug_emitente,
            )
            logger.info(f"Resposta recebida: {response}")

            response_dict: Dict[str, Any] = dict(response) if response else {}
            return response_dict
        except Exception as e:
            logger.error(f"Erro na consulta: {e}")
            return None
