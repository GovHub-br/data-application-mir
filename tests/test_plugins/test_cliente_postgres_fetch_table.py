from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from cliente_postgres import ClientPostgresDB


def _mock_connect(columns: list[str], rows: list[tuple]) -> MagicMock:
    cursor = MagicMock()
    cursor.description = [(col,) for col in columns]
    cursor.fetchall.return_value = rows
    cursor.__enter__.return_value = cursor

    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_fetch_table_retorna_lista_de_dicts_com_nome_das_colunas() -> None:
    conn = _mock_connect(["id_plano_acao", "empenhado"], [(1, 10.5), (2, None)])

    with patch("cliente_postgres.psycopg2.connect", return_value=conn):
        linhas = ClientPostgresDB("dsn").fetch_table("siafi_dbt", "planos_acao_ted")

    assert linhas == [
        {"id_plano_acao": 1, "empenhado": 10.5},
        {"id_plano_acao": 2, "empenhado": None},
    ]
    conn.cursor.return_value.execute.assert_called_once_with(
        "SELECT * FROM siafi_dbt.planos_acao_ted"
    )
    conn.close.assert_called_once()


def test_fetch_table_tabela_vazia_retorna_lista_vazia() -> None:
    conn = _mock_connect(["id"], [])

    with patch("cliente_postgres.psycopg2.connect", return_value=conn):
        assert ClientPostgresDB("dsn").fetch_table("s", "t") == []


@pytest.mark.parametrize("schema, table", [("bad;drop", "t"), ("s", "t--x"), ("", "t")])
def test_fetch_table_rejeita_identificadores_invalidos(schema: str, table: str) -> None:
    with pytest.raises(ValueError):
        ClientPostgresDB("dsn").fetch_table(schema, table)


def test_replace_rows_apaga_o_recorte_e_insere_na_mesma_transacao() -> None:
    conn = _mock_connect([], [])
    cursor = conn.cursor.return_value
    cursor.rowcount = 3
    dados = [{"nc": "A", "relatorio": "enviadas"}, {"nc": "A", "relatorio": "enviadas"}]

    with (
        patch("cliente_postgres.psycopg2.connect", return_value=conn),
        patch("cliente_postgres.psycopg2.extras.execute_values") as execute_values,
    ):
        apagadas = ClientPostgresDB("dsn").replace_rows(
            dados, "nc", "relatorio = %s", ("enviadas",), schema="siafi"
        )

    assert apagadas == 3
    cursor.execute.assert_any_call(
        "DELETE FROM siafi.nc WHERE relatorio = %s", ("enviadas",)
    )
    # linhas identicas sao inseridas as duas, sem ON CONFLICT
    sql, valores = execute_values.call_args.args[1:3]
    assert "ON CONFLICT" not in sql
    assert valores == [("A", "enviadas"), ("A", "enviadas")]
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_replace_rows_sem_dados_nao_conecta() -> None:
    with patch("cliente_postgres.psycopg2.connect") as connect:
        assert ClientPostgresDB("dsn").replace_rows([], "t", "1 = 1", ()) == 0
    connect.assert_not_called()


def test_replace_rows_rejeita_identificador_invalido() -> None:
    with pytest.raises(ValueError):
        ClientPostgresDB("dsn").replace_rows([{"a": 1}], "t; drop", "1 = 1", ())


def _exportar_csv(columns: list[str], rows: list[tuple]) -> str:
    conn = _mock_connect(columns, rows)
    with patch("cliente_postgres.psycopg2.connect", return_value=conn):
        return ClientPostgresDB("dsn").export_table_to_csv("siafi_dbt", "t")


def test_export_csv_inteiro_com_nulo_nao_vira_decimal() -> None:
    csv = _exportar_csv(["id_plano_acao", "ano"], [(1376, 2023), (2, None)])

    assert csv == "id_plano_acao,ano\n1376,2023\n2,\n"


def test_export_csv_decimal_sai_com_virgula_e_sem_perder_precisao() -> None:
    csv = _exportar_csv(
        ["valor", "taxa"], [(Decimal("1285773.68"), 99.5), (Decimal("-0.1234"), None)]
    )

    assert csv == 'valor,taxa\n"1285773,68","99,5"\n"-0,1234",\n'


@pytest.mark.parametrize(
    "texto",
    [
        "linha 1\nlinha 2",
        "linha 1\r\nlinha 2",
        "linha 1  \n\n  linha 2",
        "linha 1\x8elinha 2",  # separador de linha do SIAFI
    ],
)
def test_export_csv_quebra_de_linha_vira_um_espaco(texto: str) -> None:
    assert _exportar_csv(["obs"], [(texto,)]) == "obs\nlinha 1 linha 2\n"


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("divulgac\u0327a\u0303o", "divulgação"),  # acentos decompostos (NFD)
        ("bolsas.\u202fO CNPq", "bolsas. O CNPq"),
        ("● Justiça \uf0fc Racial", "• Justiça • Racial"),
        ("Portaria n˚ 537", "Portaria nº 537"),
        ("senƟdo hƩp", "sentido http"),
        ("BRASÍLIA \x96 DF", "BRASÍLIA – DF"),
        ("883932/2019\u200b", "883932/2019"),
        ("Paul H. O \u0301Neill", "Paul H. O ´Neill"),
    ],
)
def test_export_csv_troca_caracteres_fora_do_cp1252(texto: str, esperado: str) -> None:
    csv = _exportar_csv(["texto"], [(texto,)])

    assert csv == f"texto\n{esperado}\n"
    csv.encode("cp1252")  # nada vira "?" no envio
