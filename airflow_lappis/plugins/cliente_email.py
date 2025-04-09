import logging
import io
import zipfile
from typing import Optional, cast, List, Dict
import pandas as pd
from imap_tools import MailBox, AND
import chardet
from datetime import datetime
import pytz

# Configuração do log
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def format_csv(
    csv_data: str, column_mapping: Optional[Dict[int, str]], skiprows: int
) -> pd.DataFrame:
    """Formata um arquivo CSV conforme mapeamento de colunas."""
    if column_mapping:
        df = pd.read_csv(io.StringIO(csv_data), skiprows=skiprows, header=None)
        column_names: List[str] = [
            column_mapping.get(i, f"col_{i}") for i in range(len(df.columns))
        ]
        df.columns = pd.Index(column_names)
    else:
        df = pd.read_csv(io.StringIO(csv_data), skiprows=skiprows, header=0)
    return df


def extract_csv_from_zip(
    zip_payload: bytes, column_mapping: dict, skiprows: int = 0
) -> Optional[pd.DataFrame]:
    """Extrai e formata o primeiro arquivo CSV encontrado em um ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_payload)) as zip_file:
        for file_name in zip_file.namelist():
            if file_name.endswith(".csv"):
                raw_data = zip_file.read(file_name)
                encoding = chardet.detect(raw_data)["encoding"]
                decoded_data = raw_data.decode(encoding)
                return format_csv(decoded_data, column_mapping, skiprows)
    return None


def fetch_email_with_zip(
    imap_server: str, email: str, password: str, sender_email: str, subject: str
) -> Optional[bytes]:
    """Busca o primeiro e-mail do dia atual com um anexo ZIP."""
    today = datetime.now(pytz.timezone("America/Sao_Paulo")).date()
    with MailBox(imap_server).login(email, password) as mailbox:
        for msg in mailbox.fetch(AND(date=today, from_=sender_email, subject=subject)):
            for attachment in msg.attachments:
                if attachment.filename.endswith(".zip"):
                    return cast(bytes, attachment.payload)
    return None


def fetch_and_process_email(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: str,
    column_mapping: dict,
    skiprows: int = 0,
) -> Optional[str]:
    """Busca e processa o primeiro e-mail com um ZIP contendo um CSV formatado."""
    try:
        zip_payload = fetch_email_with_zip(
            imap_server, email, password, sender_email, subject
        )
        if zip_payload:
            csv_data = extract_csv_from_zip(zip_payload, column_mapping, skiprows)
            if csv_data is not None:
                return csv_data.to_csv(index=False)
        logging.warning("Nenhum CSV processado.")
    except Exception as e:
        logging.error(f"Erro ao processar e-mails: {e}")
    return None
