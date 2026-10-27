from unittest.mock import MagicMock, patch

import pytest

from cliente_onedrive import ClienteOneDrive

BASE = "DAMGI/Plaforma Maria Firmina"


@pytest.mark.parametrize(
    ("parts", "esperado"),
    [
        ((BASE, "TEDs"), f"{BASE}/TEDs"),
        ((BASE, None), BASE),
        ((BASE, ""), BASE),
        ((f"{BASE}/", "/TEDs/"), f"{BASE}/TEDs"),
        ((BASE, "Indicadores/I7"), f"{BASE}/Indicadores/I7"),
        (("", "TEDs"), "TEDs"),
        (("", None), ""),
        (("/", "/"), ""),
    ],
)
def test_join_path_ignora_vazios_e_barras_nas_pontas(parts: tuple, esperado: str) -> None:
    assert ClienteOneDrive.join_path(*parts) == esperado


def test_item_path_sem_pasta_e_so_o_arquivo() -> None:
    assert ClienteOneDrive._item_path("", "planos_acao_ted.csv") == "planos_acao_ted.csv"


def test_upload_vai_para_a_subpasta_relativa_a_base() -> None:
    token = MagicMock()
    token.json.return_value = {"access_token": "tok"}
    put = MagicMock()
    put.json.return_value = {"id": "item"}
    cliente = ClienteOneDrive("client", "secret", "tenant")

    with (
        patch("cliente_onedrive.requests.post", return_value=token),
        patch("cliente_onedrive.requests.put", return_value=put) as mock_put,
    ):
        cliente.upload_file(
            user_id="user",
            folder_path=ClienteOneDrive.join_path(BASE, "Convênios"),
            file_name="resumo_convenios.csv",
            content=b"a,b\n",
        )

    assert mock_put.call_args.args[0] == (
        "https://graph.microsoft.com/v1.0/users/user/drive/root:/"
        "DAMGI/Plaforma%20Maria%20Firmina/Conv%C3%AAnios/resumo_convenios.csv:/content"
    )
