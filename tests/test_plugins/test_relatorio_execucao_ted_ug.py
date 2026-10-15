import pytest

from relatorio_execucao_ted_ug import COLUMNS, decodificar, parse_execucao_ted_ug


def _linha(*campos: str) -> str:
    return "\t".join(f'"{c}"' if c else "" for c in campos)


CABECALHO = _linha(
    "Ano Lançamento", "Órgão UGE", "", "UG Executora", "", "Ação Governo", "",
    "Plano Orçamentário", "", "PTRES", "Grupo Despesa", "Item Informação",
    "DESTAQUE RECEBIDO", "CREDITO DISPONIVEL", "DESPESAS EMPENHADAS",
    "DESPESAS LIQUIDADAS", "DESPESAS PAGAS",
)  # fmt: skip
SUBCABECALHO = "\t".join(
    [" "] * 11 + ['"Fonte Recursos Detalhada"'] + ['"Saldo - R$ (Item Informação)"'] * 5
)
DADO_ENAP = _linha(
    "2026", "20202", "FUNDACAO ESCOLA NACIONAL DE ADM. PUBLICA", "114702",
    "FUNDACAO ESCOLA NACIONAL DE ADM. PUBLICA", "21FC", "MONITORAMENTO",
    "0001", "MONITORAMENTO, AVALIACAO", "233518", "3", "1000A003OQ",
    "102.213,06", "76.331,49", "25.881,57", "14.763,96", "13.533,49",
)  # fmt: skip
DADO_CNPQ = _linha(
    "2026", "20501", "CONSELHO NACIONAL DE DES.CIENT.E TECNOLOGICO", "364102",
    "CONSELHO NAC DE DESENV CIENT E TECNOLOGICO", "21HN", "GESTAO", "0001",
    "FORTALECIMENTO", "250250", "3", "1000A003OO", "500.000,00", "50.000,00",
    "450.000,00", "", "",
)  # fmt: skip
TOTAL_UG = (
    '"2026"\t"20202"\t"FUNDACAO ESCOLA NACIONAL DE ADM. PUBLICA"\t"114702"\t'
    '"FUNDACAO ESCOLA NACIONAL DE ADM. PUBLICA"\t"Total"\t\t""\t\t""\t""\t""\t'
    '"102.213,06"\t"76.331,49"\t"25.881,57"\t"14.763,96"\t"13.533,49"'
)
TOTAL_ANO = (
    '"2026"\t"Total"\t\t""\t\t""\t\t""\t\t""\t""\t""\t'
    '"602.213,06"\t"126.331,49"\t"475.881,57"\t"14.763,96"\t"13.533,49"'
)
TITULO = [
    "MINISTÉRIO DAS RELAÇÕES EXTERIORES - MRE",
    "ORÇAMENTO LIBERADO, PELA COF, PARA AS UG'S EXECUTORAS ATÉ 30 DE JULHO DE 2021",
    "DESPESAS DISCRICIONÁRIAS 2021",
]


def _relatorio(*linhas: str) -> str:
    return "\r\n".join([*TITULO, CABECALHO, SUBCABECALHO, *linhas, ""])


def test_le_as_linhas_de_dado_e_ignora_titulo_e_totais() -> None:
    registros = parse_execucao_ted_ug(
        _relatorio(DADO_ENAP, TOTAL_UG, DADO_CNPQ, TOTAL_ANO)
    )

    assert len(registros) == 2
    assert list(registros[0]) == COLUMNS
    enap = registros[0]
    assert enap["ano_lancamento"] == "2026"
    assert enap["ug_executora_codigo"] == "114702"
    assert enap["acao_governo_codigo"] == "21FC"
    assert enap["plano_orcamentario_codigo"] == "0001"
    assert enap["ptres"] == "233518"
    assert enap["fonte_recursos_detalhada"] == "1000A003OQ"
    assert enap["destaque_recebido"] == "102.213,06"
    assert enap["credito_disponivel"] == "76.331,49"
    assert enap["despesas_pagas"] == "13.533,49"


def test_valor_vazio_vira_none() -> None:
    (cnpq,) = parse_execucao_ted_ug(_relatorio(DADO_CNPQ))

    assert cnpq["despesas_empenhadas"] == "450.000,00"
    assert cnpq["despesas_liquidadas"] is None
    assert cnpq["despesas_pagas"] is None


def test_falha_se_o_cabecalho_mudar() -> None:
    relatorio = _relatorio(DADO_ENAP).replace("CREDITO DISPONIVEL", "SALDO")

    with pytest.raises(ValueError, match="CREDITO DISPONIVEL"):
        parse_execucao_ted_ug(relatorio)


def test_falha_se_a_fonte_sair_do_subcabecalho() -> None:
    relatorio = _relatorio(DADO_ENAP).replace("Fonte Recursos Detalhada", "Natureza")

    with pytest.raises(ValueError, match="Fonte Recursos Detalhada"):
        parse_execucao_ted_ug(relatorio)


def test_falha_sem_cabecalho() -> None:
    with pytest.raises(ValueError, match="Cabeçalho"):
        parse_execucao_ted_ug("\r\n".join(TITULO))


def test_descarta_linha_com_largura_inesperada() -> None:
    registros = parse_execucao_ted_ug(_relatorio(DADO_ENAP, DADO_ENAP + '\t"extra"'))

    assert len(registros) == 1


def test_decodifica_utf16_com_bom_como_vem_do_tesouro() -> None:
    texto = _relatorio(DADO_ENAP)
    raw = texto.encode("utf-16")  # com BOM, como no anexo do Tesouro

    (enap,) = parse_execucao_ted_ug(decodificar(raw))

    assert enap["orgao_uge_nome"] == "FUNDACAO ESCOLA NACIONAL DE ADM. PUBLICA"
    assert enap["acao_governo_codigo"] == "21FC"


def test_decodifica_latin1_sem_bom() -> None:
    raw = _relatorio(DADO_ENAP).encode("latin-1")

    assert len(parse_execucao_ted_ug(decodificar(raw))) == 1
