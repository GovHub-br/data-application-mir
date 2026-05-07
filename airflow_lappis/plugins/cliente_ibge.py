import io
import logging
from contextlib import contextmanager

# ftp.ibge.gov.br é um servidor público do governo
# brasileiro que não oferece suporte a FTPS/SFTP. Apenas dados
# públicos e anônimos são trafegados nessa conexão.
from ftplib import FTP  # NOSONAR

from cliente_base import ClienteBase


class ClienteIBGE(ClienteBase):
    FTP_HOST = "ftp.ibge.gov.br"
    BASE_DIR = "/Censos/Censo_Demografico_2022/"

    def __init__(self, database: str) -> None:
        self.host = ClienteIBGE.FTP_HOST
        self.database = database
        logging.info("[cliente_ibge] Inicializando conexão FTP com: %s", self.host)

    @contextmanager
    def _conectar(self):
        """
        Abre uma conexão FTP com o servidor público do IBGE.

        Uso:
            with self._conectar() as ftp:
                ftp.nlst()
        """
        full_path = f"{self.BASE_DIR.rstrip('/')}/{self.database.lstrip('/')}"
        ftp = FTP(timeout=30)  # NOSONAR
        try:
            ftp.connect(self.host)
            resp = ftp.login(user="anonymous", passwd="anonymous@")
            logging.info("[cliente_ibge] FTP login: %s", resp)
            ftp.set_pasv(True)
            ftp.cwd(full_path)
            yield ftp
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    # Interface pública
    def listar_arquivos_alvo(self) -> list[str]:
        """Lista arquivos Excel/CSV do diretório do Censo 2022."""
        try:
            with self._conectar() as ftp:
                arquivos = ftp.nlst()

            filtrados = [f for f in arquivos if f.endswith((".xlsx", ".xls", ".csv"))]
            logging.info("[cliente_ibge] %d arquivo(s) encontrado(s).", len(filtrados))
            return filtrados

        except Exception as exc:
            logging.error("[cliente_ibge] Erro ao listar arquivos: %s", exc)
            return []

    def obter_conteudo_arquivo(self, nome_arquivo: str) -> io.BytesIO | None:
        """Baixa um arquivo do FTP diretamente para memória."""
        buffer = io.BytesIO()
        try:
            with self._conectar() as ftp:
                logging.info("[cliente_ibge] Baixando: %s", nome_arquivo)
                ftp.retrbinary(f"RETR {nome_arquivo}", buffer.write)

            buffer.seek(0)
            return buffer

        except Exception as exc:
            logging.error("[cliente_ibge] Erro ao baixar '%s': %s", nome_arquivo, exc)
            return None
