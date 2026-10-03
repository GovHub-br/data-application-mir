from unittest.mock import MagicMock, patch

import httpx
import pytest

from cliente_transferencias_gov_br import (
    ClienteTransferenciasGovBr,
    extrair_teds,
    html_para_texto,
)

PAGINA_HTML = """
<html><body>
<div id="portal-header">Termo de Execução Descentralizada nº 99/2099</div>
<div id="content-core">
<h3>Termo de Execução Descentralizada nº 5/2026 - Transferegov n° 996644</h3>
<p>Termo de Execução Descentralizada nº 05/2026 - MIR X UFG - Transferegov n° 996694, \
firmado entre o Ministério da Igualdade Racial - MIR e a Universidade Federal de \
Goiás - UFG. Processo: 21290.004335/2025-15. Objeto: "Ações", no valor de \
R$ 5.011.700,00 (cinco milhões).</p>
<h3>Termo de Execução Descentralizada nº 12/2024 - Transferegov n° 7AABPO</h3>
<p>Termo de Execução Descentralizada nº 12/2024 firmado entre o Ministério da \
Igualdade Racial - MIR e a Fundação Oswaldo Cruz. Processo: 21290.201320/2024-12. \
Valor de R$&nbsp;1.000.000,00.</p>
<h3>TED da UFF nº 3/2025</h3>
<p>Sem número do Transferegov.</p>
</div>
<div id="viewlet-below-content">Termo de Execução Descentralizada nº 98/2098</div>
</body></html>
"""

PAGINA_PRINCIPAL_HTML = """
<a href="https://www.gov.br/x/tranferencias-voluntarias/2026-1">2026</a>
<a href="https://www.gov.br/x/tranferencias-voluntarias/2024/">2024</a>
<a href="https://www.gov.br/x/tranferencias-voluntarias/2024">2024 de novo</a>
<a href="https://www.gov.br/x/tranferencias-voluntarias/transferencias-voluntarias-1">
"""


@pytest.fixture
def cliente() -> ClienteTransferenciasGovBr:
    with patch("cliente_base.httpx.Client"):
        return ClienteTransferenciasGovBr()


# ---------------------------------------------------------------------------
# html_para_texto / extrair_teds
# ---------------------------------------------------------------------------
def test_html_para_texto_le_so_o_corpo_da_pagina() -> None:
    texto = html_para_texto(PAGINA_HTML)

    assert "99/2099" not in texto
    assert "98/2098" not in texto
    assert "R$ 1.000.000,00" in texto  # &nbsp; vira espaço


def test_html_para_texto_sem_corpo_devolve_vazio() -> None:
    assert html_para_texto("<html><body>nada</body></html>") == ""


def test_extrair_teds_um_registro_por_ted() -> None:
    teds = extrair_teds(html_para_texto(PAGINA_HTML), "2026-1")

    assert [t["numero_ted"] for t in teds] == ["05/2026", "12/2024", "03/2025"]
    assert all(t["pagina"] == "2026-1" for t in teds)


def test_extrair_teds_primeiro_numero_e_o_do_titulo() -> None:
    ted = extrair_teds(html_para_texto(PAGINA_HTML), "2026-1")[0]

    assert ted["num_transf"] == "996644"
    assert ted["num_transf_alternativos"] == "996694"
    assert ted["processo"] == "21290.004335/2025-15"
    assert ted["parceiro"] == "Universidade Federal de Goiás - UFG"
    assert ted["valor"] == "5.011.700,00"


def test_extrair_teds_numero_alfanumerico_de_2026() -> None:
    ted = extrair_teds(html_para_texto(PAGINA_HTML), "2026-1")[1]

    assert ted["num_transf"] == "7AABPO"
    assert ted["num_transf_alternativos"] is None
    assert ted["parceiro"] == "Fundação Oswaldo Cruz"


def test_extrair_teds_sem_numero_do_transferegov() -> None:
    ted = extrair_teds(html_para_texto(PAGINA_HTML), "2026-1")[2]

    assert ted["num_transf"] is None
    assert ted["processo"] is None
    assert ted["valor"] is None
    assert ted["texto"].startswith("TED da UFF nº 3/2025")


# ---------------------------------------------------------------------------
# ClienteTransferenciasGovBr
# ---------------------------------------------------------------------------
def test_init_sets_base_url_e_headers() -> None:
    with patch("cliente_base.httpx.Client") as mock_client:
        cliente = ClienteTransferenciasGovBr()

    assert cliente.base_url == ClienteTransferenciasGovBr.BASE_URL
    mock_client.assert_called_once_with(
        base_url=ClienteTransferenciasGovBr.BASE_URL,
        headers=ClienteTransferenciasGovBr.BASE_HEADER,
    )


def test_get_html_devolve_o_texto(cliente: ClienteTransferenciasGovBr) -> None:
    cliente.client.get.return_value = MagicMock(text="<html/>")

    assert cliente.get_html("/2024") == "<html/>"
    cliente.client.get.assert_called_once_with("/2024", timeout=30)


def test_get_html_tenta_de_novo_e_desiste(
    cliente: ClienteTransferenciasGovBr,
) -> None:
    cliente.client.get.side_effect = httpx.ConnectError("falhou")

    with patch("cliente_transferencias_gov_br.time.sleep"):
        with pytest.raises(Exception, match="número máximo de tentativas"):
            cliente.get_html("/2024")

    assert cliente.client.get.call_count == cliente.DEFAULT_MAX_RETRIES + 1


def test_listar_paginas_so_anos_sem_repetir(
    cliente: ClienteTransferenciasGovBr,
) -> None:
    with patch.object(cliente, "get_html", return_value=PAGINA_PRINCIPAL_HTML):
        assert cliente.listar_paginas() == ["2026-1", "2024"]


def test_get_teds_pagina_inclui_url(cliente: ClienteTransferenciasGovBr) -> None:
    with patch.object(cliente, "get_html", return_value=PAGINA_HTML) as mock_get:
        teds = cliente.get_teds_pagina("2026-1")

    mock_get.assert_called_once_with("/2026-1")
    assert len(teds) == 3
    assert teds[0]["url"] == f"{ClienteTransferenciasGovBr.BASE_URL}/2026-1"
