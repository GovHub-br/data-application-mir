from unittest.mock import patch, MagicMock
from airflow_lappis.plugins.cliente_email import process_email_attachments
from airflow_lappis.plugins.cliente_email import fetch_emails
import pandas as pd
from imap_tools import MailMessage


def test_fetch_emails_success():
    # Simula a conexão com o servidor IMAP
    with patch("airflow_lappis.plugins.cliente_email.MailBox") as mock_mailbox:
        # Cria um mock de e-mail com os atributos esperados
        mock_email = MagicMock(spec=MailMessage)
        mock_email.subject = "Test Subject"
        mock_email.from_ = "test@example.com"

        # Configura o mock do MailBox
        mock_mailbox_instance = mock_mailbox.return_value
        mock_login = mock_mailbox_instance.login.return_value
        mock_mailbox_context = mock_login.__enter__.return_value
        mock_mailbox_context.fetch.return_value = iter([mock_email])

        # Executa a função
        result = fetch_emails(
            imap_server="imap.example.com",
            email="user@example.com",
            password="password",
            sender_email="test@example.com",
            subject="Test Subject",
        )

        # Verifica o resultado
        assert result is not None
        assert result.subject == "Test Subject"


def test_process_email_attachments_success():
    # Simula um e-mail com anexo ZIP
    mock_email = MagicMock()
    mock_email.attachments = [MagicMock(filename="test.zip", payload=b"fake_zip_data")]

    # Simula a extração do CSV do ZIP
    with patch(
        "airflow_lappis.plugins.cliente_email.extract_csv_from_zip"
    ) as mock_extract:
        mock_extract.return_value = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

        # Executa a função
        result = process_email_attachments(
            mock_email, column_mapping={0: "col1", 1: "col2"}
        )

        # Verifica o resultado
        assert result is not None
        assert not result.empty
