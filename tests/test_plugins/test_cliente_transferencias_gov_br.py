import importlib.util
import logging
import os
import sys
from unittest.mock import MagicMock, patch

import httpx
import pytest

from cliente_transferencias_gov_br import (
    ClienteTransferenciasGovBr,
    documento_para_texto,
    extrair_descentralizacoes,
    extrair_teds,
    html_para_texto,
)

PAGINA_HTML = """
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
"""

# Página com TED seguido de descentralizações sem TED (tedinhos), como a de 2025
PAGINA_DESCENTRALIZACOES_HTML = """
<h3>Termo de Execução Descentralizada nº 01/2025 - Transferegov n° 974892</h3>
<p>Termo de Execução Descentralizada nº 01/2025 firmado entre o Ministério da \
Igualdade Racial - MIR e a Universidade Federal Fluminense - UFF. Processo: \
21290.000100/2025-10. Valor de R$ 629.282,00.</p>
<h3>Descentralização de Crédito</h3>
<p>Descentralização de crédito firmado entre o Ministério da Igualdade Racial - \
MIR e a Fundação Escola Nacional de Administração Pública - Enap. Processo: \
21290.001270/2025-56. Objeto: "Prestação do serviço Evidência Express (EvEx)", no \
valor total de R$ 118.267,00 (cento e dezoito mil). Vigência: 2025 a 2026.</p>
<p>Acesse a íntegra desse Plano de Trabalho</p>
<h3>Descentralização de Crédito </h3>
<p>Descentralização de crédito firmado entre o Ministério da Igualdade Racial - \
MIR e o Instituto Federal de Goiás - IFG. Processo: 21290.001747/2025-01. Objeto: \
"Organizar um estande formativo", no valor total de R$ 100.000,00.</p>
<h3>Descentralização de Crédito</h3>
<p>Em elaboração.</p>
"""

URL_PAGINAS = "https://www.gov.br/x/tranferencias-voluntarias"


def _card(pagina: str) -> dict:
    return {"cards": [{"source": [{"@id": f"{URL_PAGINAS}/{pagina}", "title": pagina}]}]}


# Página principal do portal: os anos são cards dentro de colunas, e o corpo do
# documento também lista os anexos da pasta (formato de ++api++ desde 10/2026).
DOCUMENTO_PRINCIPAL = {
    "@id": URL_PAGINAS,
    "blocks": {
        "colunas": {
            "@type": "columnsBlock",
            "data": {
                "blocks": {"c1": {"blocks": {"a": _card("2026-1"), "b": _card("2024")}}}
            },
        }
    },
    "blocks_layout": {"items": ["colunas"]},
    "items": [
        {"@id": f"{URL_PAGINAS}/transferencias-voluntarias-1", "@type": "Link"},
        {"@id": f"{URL_PAGINAS}/2024/", "@type": "Document"},
        {"@id": f"{URL_PAGINAS}/Plano_de_Trabalho_2024.pdf", "@type": "File"},
    ],
}

# Só os anexos, sem nenhum link de subpágina por ano.
DOCUMENTO_PRINCIPAL_SEM_SUBPAGINAS = {
    "@id": URL_PAGINAS,
    "blocks": {"texto": {"@type": "slate", "value": []}},
    "blocks_layout": {"items": ["texto"]},
    "items": [
        {"@id": f"{URL_PAGINAS}/transferencias-voluntarias-1", "@type": "Link"},
        {"@id": f"{URL_PAGINAS}/Plano_de_Trabalho_2024.pdf", "@type": "File"},
    ],
}

# O plaintext do Slate cola o título no parágrafo ("...946708Termo..."): as quebras
# de linha só existem na árvore de nós.
BLOCO_SLATE = {
    "@type": "slate",
    "plaintext": "Termo de Execução Descentralizada nº 01/2023 - Transferegov nº "
    "946708Termo de Execução Descentralizada nº 01/2023, firmado entre o Ministério "
    "da Igualdade Racial - MIR e a Universidade de Brasília/UnB.",
    "value": [
        {
            "type": "callout",
            "children": [
                {
                    "type": "strong",
                    "children": [
                        {
                            "text": "Termo de Execução Descentralizada nº 01/2023 - "
                            "Transferegov nº 946708"
                        }
                    ],
                },
                {
                    "text": "\n\nTermo de Execução Descentralizada nº 01/2023, firmado "
                    "entre o Ministério da Igualdade Racial - MIR e a Universidade de "
                    'Brasília/UnB. Processo: 21290.201747/2023-30. Objeto: "Promover '
                    'atividades", no valor total de R$ 352.800,00.\n\nAcesse a '
                    "íntegra desse "
                },
                {
                    "type": "link",
                    "data": {"url": f"{URL_PAGINAS}/TED01.pdf"},
                    "children": [{"text": "Termo de Execução"}],
                },
            ],
        }
    ],
}

BLOCO_HTML = {
    "@type": "html",
    "html": '<p class="callout"><!--StartFragment--><span><strong>Termo de Execução '
    "Descentralizada nº 02/2023 -&nbsp;Transferegov n° 945101</strong><br><br>Termo "
    "de Execução Descentralizada nº 02/2023, firmado entre o Ministério da Igualdade "
    "Racial - MIR e a Fundação IBGE. Processo: 21290.202080/2023-92. Valor de "
    "R$&nbsp;1.000,00.</span></p>",
}

BLOCO_DESCENTRALIZACAO_SLATE = {
    "@type": "slate",
    "value": [
        {
            "type": "p",
            "children": [
                {"type": "strong", "children": [{"text": "Descentralização de Crédito"}]},
                {
                    "text": "\n\nDescentralização de crédito firmado entre o Ministério "
                    "da Igualdade Racial - MIR e o Instituto Federal de Goiás - IFG. "
                    'Processo: 21290.001747/2025-01. Objeto: "Estande", no valor total '
                    "de R$ 100.000,00."
                },
            ],
        }
    ],
}


def _documento(*blocos: dict, **extras: str) -> dict:
    """Documento do portal com os blocos na ordem do layout, depois do cabeçalho."""
    cabecalho = [{"@type": t} for t in ("title", "description", "dateSocialShareBlock")]
    todos = {f"b{i}": b for i, b in enumerate([*cabecalho, *blocos])}
    return {"blocks": todos, "blocks_layout": {"items": list(todos)}, **extras}


DOCUMENTO = _documento(BLOCO_SLATE, BLOCO_HTML)


@pytest.fixture
def cliente() -> ClienteTransferenciasGovBr:
    with patch("cliente_base.httpx.Client"):
        return ClienteTransferenciasGovBr()


# ---------------------------------------------------------------------------
# html_para_texto / documento_para_texto
# ---------------------------------------------------------------------------
def test_html_para_texto_tira_tags_e_entidades() -> None:
    texto = html_para_texto(PAGINA_HTML)

    assert "<" not in texto
    assert "R$ 1.000.000,00" in texto  # &nbsp; vira espaço


def test_documento_para_texto_segue_a_ordem_do_layout() -> None:
    documento = {
        "blocks": {"a": BLOCO_HTML, "b": BLOCO_SLATE, "fora_do_layout": BLOCO_HTML},
        "blocks_layout": {"items": ["b", "a"]},
    }

    (slate, html_ted) = extrair_teds(documento_para_texto(documento), "2023")

    assert slate["numero_ted"] == "01/2023"
    assert html_ted["numero_ted"] == "02/2023"


def test_documento_para_texto_nao_le_titulo_nem_data() -> None:
    documento = _documento(BLOCO_HTML)
    documento["blocks"]["b0"]["title"] = "Termo de Execução Descentralizada nº 99/2099"

    assert "99/2099" not in documento_para_texto(documento)


def test_documento_para_texto_separa_titulo_do_paragrafo_no_slate() -> None:
    primeira, segunda, _ = documento_para_texto(_documento(BLOCO_SLATE)).splitlines()

    assert primeira.strip().endswith("Transferegov nº 946708")
    assert segunda.strip().startswith("Termo de Execução Descentralizada nº 01/2023,")


def test_documento_para_texto_avisa_de_bloco_desconhecido(
    caplog: pytest.LogCaptureFixture,
) -> None:
    documento = _documento(BLOCO_HTML, {"@type": "columnsBlock"}, **{"@id": "/2023"})

    with caplog.at_level(logging.WARNING):
        texto = documento_para_texto(documento)

    assert "02/2023" in texto
    assert "Bloco columnsBlock ignorado em /2023" in caplog.text


def test_documento_para_texto_sem_blocos_devolve_vazio() -> None:
    assert documento_para_texto({}) == ""


# ---------------------------------------------------------------------------
# extrair_teds
# ---------------------------------------------------------------------------
def test_extrair_teds_de_blocos_slate_e_html() -> None:
    slate, html_ted = extrair_teds(documento_para_texto(DOCUMENTO), "2023")

    assert slate["num_transf"] == "946708"
    assert slate["num_transf_alternativos"] is None
    assert slate["processo"] == "21290.201747/2023-30"
    assert slate["parceiro"] == "Universidade de Brasília/UnB"
    assert slate["valor"] == "352.800,00"
    assert "Acesse a íntegra desse Termo de Execução" in slate["texto"]
    assert html_ted["num_transf"] == "945101"
    assert html_ted["parceiro"] == "Fundação IBGE"
    assert html_ted["valor"] == "1.000,00"


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


def test_extrair_teds_para_na_descentralizacao_seguinte() -> None:
    (ted,) = extrair_teds(html_para_texto(PAGINA_DESCENTRALIZACOES_HTML), "2025-1")

    assert ted["numero_ted"] == "01/2025"
    assert ted["num_transf"] == "974892"
    assert "Enap" not in ted["texto"]


# ---------------------------------------------------------------------------
# extrair_descentralizacoes
# ---------------------------------------------------------------------------
def test_extrair_descentralizacoes_um_registro_por_bloco() -> None:
    descs = extrair_descentralizacoes(
        html_para_texto(PAGINA_DESCENTRALIZACOES_HTML), "2025-1"
    )

    # o bloco "Em elaboração" não tem o parágrafo do instrumento e fica de fora
    assert [d["processo"] for d in descs] == [
        "21290.001270/2025-56",
        "21290.001747/2025-01",
    ]
    assert all(d["pagina"] == "2025-1" for d in descs)


def test_extrair_descentralizacoes_campos() -> None:
    enap, ifg = extrair_descentralizacoes(
        html_para_texto(PAGINA_DESCENTRALIZACOES_HTML), "2025-1"
    )

    assert enap["parceiro"] == "Fundação Escola Nacional de Administração Pública - Enap"
    assert enap["objeto"] == "Prestação do serviço Evidência Express (EvEx)"
    assert enap["valor"] == "118.267,00"
    assert ifg["parceiro"] == "Instituto Federal de Goiás - IFG"
    assert ifg["valor"] == "100.000,00"


def test_extrair_descentralizacoes_de_bloco_slate() -> None:
    texto = documento_para_texto(_documento(BLOCO_HTML, BLOCO_DESCENTRALIZACAO_SLATE))

    ted = extrair_teds(texto, "2025-1")
    desc = extrair_descentralizacoes(texto, "2025-1")

    assert [t["numero_ted"] for t in ted] == ["02/2023"]
    assert "IFG" not in ted[0]["texto"]
    assert [d["processo"] for d in desc] == ["21290.001747/2025-01"]
    assert desc[0]["parceiro"] == "Instituto Federal de Goiás - IFG"
    assert desc[0]["objeto"] == "Estande"
    assert desc[0]["valor"] == "100.000,00"


def test_extrair_descentralizacoes_pagina_sem_nenhuma() -> None:
    assert extrair_descentralizacoes(html_para_texto(PAGINA_HTML), "2026-1") == []


# ---------------------------------------------------------------------------
# ClienteTransferenciasGovBr
# ---------------------------------------------------------------------------
def test_init_aponta_para_a_api_do_portal() -> None:
    with patch("cliente_base.httpx.Client") as mock_client:
        cliente = ClienteTransferenciasGovBr()

    assert "/igualdaderacial/++api++/pt-br/" in cliente.base_url
    mock_client.assert_called_once_with(
        base_url=ClienteTransferenciasGovBr.BASE_URL,
        headers=ClienteTransferenciasGovBr.BASE_HEADER,
    )


def test_get_documento_devolve_o_json(cliente: ClienteTransferenciasGovBr) -> None:
    cliente.client.request.return_value = MagicMock(
        status_code=200, json=lambda: DOCUMENTO
    )

    assert cliente.get_documento("/2024") == DOCUMENTO
    cliente.client.request.assert_called_once_with("GET", "/2024", timeout=30)


def test_get_documento_tenta_de_novo_e_desiste(
    cliente: ClienteTransferenciasGovBr,
) -> None:
    cliente.client.request.side_effect = httpx.ConnectError("falhou")

    with patch("cliente_base.time.sleep"):
        with pytest.raises(Exception, match="maximum number of attempts"):
            cliente.get_documento("/2024")

    assert cliente.client.request.call_count == cliente.DEFAULT_MAX_RETRIES + 1


def test_listar_paginas_so_anos_sem_repetir(
    cliente: ClienteTransferenciasGovBr,
) -> None:
    with patch.object(cliente, "get_documento", return_value=DOCUMENTO_PRINCIPAL):
        assert cliente.listar_paginas() == ["2026-1", "2024"]


@pytest.mark.parametrize("documento", [DOCUMENTO_PRINCIPAL_SEM_SUBPAGINAS, {}])
def test_listar_paginas_sem_subpaginas_devolve_vazio(
    cliente: ClienteTransferenciasGovBr, documento: dict
) -> None:
    with patch.object(cliente, "get_documento", return_value=documento):
        assert cliente.listar_paginas() == []


def test_get_teds_pagina_inclui_url_publica(cliente: ClienteTransferenciasGovBr) -> None:
    with patch.object(cliente, "get_documento", return_value=DOCUMENTO) as mock_get:
        teds = cliente.get_teds_pagina("2023")

    mock_get.assert_called_once_with("/2023")
    assert len(teds) == 2
    assert teds[0]["url"] == f"{ClienteTransferenciasGovBr.URL_PUBLICA}/2023"
    assert "++api++" not in teds[0]["url"]


def test_get_transferencias_pagina_le_a_pagina_uma_vez(
    cliente: ClienteTransferenciasGovBr,
) -> None:
    documento = _documento(BLOCO_HTML, BLOCO_DESCENTRALIZACAO_SLATE)
    with patch.object(cliente, "get_documento", return_value=documento) as mock_get:
        teds, descs = cliente.get_transferencias_pagina("2025-1")

    mock_get.assert_called_once_with("/2025-1")
    assert len(teds) == 1
    assert len(descs) == 1
    assert descs[0]["url"] == f"{ClienteTransferenciasGovBr.URL_PUBLICA}/2025-1"


# ---------------------------------------------------------------------------
# DAG teds_gov_br_mir_dag
# ---------------------------------------------------------------------------
def _rodar_dag(api: MagicMock, db: MagicMock) -> None:
    """
    Carrega o módulo da DAG sem Airflow: com dag e task como identidade, o import
    já executa a task, usando os clientes falsos.
    """
    decorators = MagicMock()
    decorators.dag = lambda **_: lambda funcao: funcao
    decorators.task = lambda funcao: funcao
    stubs = {
        "airflow": MagicMock(),
        "airflow.decorators": decorators,
        "schedule_loader": MagicMock(),
        "postgres_helpers": MagicMock(),
        "cliente_transferencias_gov_br": MagicMock(
            ClienteTransferenciasGovBr=lambda: api
        ),
        "cliente_postgres": MagicMock(ClientPostgresDB=lambda _: db),
    }
    caminho = os.path.join(
        os.path.dirname(__file__),
        "../../airflow_lappis/dags/data_ingest/transfere_gov/mir/"
        "teds_gov_br_ingest_mir_dag.py",
    )
    spec = importlib.util.spec_from_file_location("teds_gov_br_dag", caminho)
    assert spec is not None and spec.loader is not None
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(importlib.util.module_from_spec(spec))


def test_dag_sem_subpaginas_falha_e_nao_grava() -> None:
    api, db = MagicMock(), MagicMock()
    api.listar_paginas.return_value = []

    with pytest.raises(ValueError, match="Nenhuma subpágina"):
        _rodar_dag(api, db)

    db.insert_data.assert_not_called()


def test_dag_grava_retrato_com_mesmo_dt_ingest() -> None:
    api, db = MagicMock(), MagicMock()
    api.listar_paginas.return_value = ["2023", "2025-1"]
    api.get_transferencias_pagina.side_effect = [
        ([{"numero_ted": "01/2023"}, {"numero_ted": "02/2023"}], []),
        ([{"numero_ted": "01/2025"}], [{"processo": "21290.001747/2025-01"}]),
    ]

    _rodar_dag(api, db)

    teds = db.insert_data.call_args_list[0]
    descs = db.insert_data.call_args_list[1]
    assert teds.args[1] == "teds_gov_br"
    assert [(r["numero_ted"], r["ordem"]) for r in teds.args[0]] == [
        ("01/2023", 1),
        ("02/2023", 2),
        ("01/2025", 1),
    ]
    assert descs.args[1] == "descentralizacoes_gov_br"
    assert {r["dt_ingest"] for r in teds.args[0] + descs.args[0]} == {
        teds.args[0][0]["dt_ingest"]
    }
