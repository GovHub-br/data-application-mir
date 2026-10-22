import logging
from dataclasses import dataclass

from cliente_postgres import ClientPostgresDB
from cliente_ted import ClienteTed

SCHEMA = "transfere_gov"


@dataclass(frozen=True)
class EndpointTed:
    """Um endpoint da API de TED filtrado por ids ja gravados no Postgres.

    ordem: ordem total das linhas, exigida pela paginacao da API.

    Toda carga substitui a tabela inteira: get_por_ids devolve o retrato completo
    (ou None), e um upsert pela chave natural manteria para sempre as linhas
    removidas na fonte. Por isso nao ha campo de chave aqui; a chave natural de
    cada tabela fica documentada (e testada) no bronze do dbt.
    """

    tabela_api: str
    coluna_filtro: str
    tabela_ids: str
    coluna_ids: str
    tabela_destino: str
    ordem: str


# plano_acao_etapa depois de plano_acao_meta: os ids dela saem da tabela da meta.
ENDPOINTS_TED: tuple[EndpointTed, ...] = (
    EndpointTed(
        "plano_acao_meta",
        "id_plano_acao",
        "planos_acao",
        "id_plano_acao",
        "planos_acao_meta",
        "id_meta",
    ),
    EndpointTed(
        "plano_acao_etapa",
        "id_meta",
        "planos_acao_meta",
        "id_meta",
        "planos_acao_etapa",
        "id_etapa",
    ),
    EndpointTed(
        "termo_execucao",
        "id_plano_acao",
        "planos_acao",
        "id_plano_acao",
        "termos_execucao",
        "id_termo",
    ),
    EndpointTed(
        "plano_acao_analise",
        "id_plano_acao",
        "planos_acao",
        "id_plano_acao",
        "planos_acao_analise",
        "id_analise",
    ),
    EndpointTed(
        "plano_acao_parecer",
        "id_plano_acao",
        "planos_acao",
        "id_plano_acao",
        "planos_acao_parecer",
        "id_parecer",
    ),
    EndpointTed(
        "evento",
        "id_nota",
        "notas_de_credito",
        "id_nota",
        "eventos_nota_credito",
        "id_nota,cd_evento,cd_ptres_evento,cd_fonte_recurso_evento,"
        "cd_plano_interno_evento,codigo_natureza,cd_ug_responsavel_evento,vl_evento",
    ),
    EndpointTed(
        "trf",
        "id_programacao",
        "programacao_financeira",
        "id_programacao",
        "trf_programacao_financeira",
        "id_programacao,cd_vinculacao_trf,cd_fonte_recurso_trf,"
        "cd_categoria_gasto_trf,cd_situacao_contabil_trf,vl_valor_trf",
    ),
    EndpointTed(
        "programa_acao_orcamentaria",
        "id_programa",
        "programas",
        "id_programa",
        "programas_acao_orcamentaria",
        "id_programa,tx_codigo_acao_orcamentaria",
    ),
    EndpointTed(
        "programa_beneficiario",
        "id_programa",
        "programas",
        "id_programa",
        "programas_beneficiario",
        "id_programa,tx_codigo_siorg,vl_valor_beneficiario,tx_nome_beneficiario",
    ),
)


def _ids(db: ClientPostgresDB, endpoint: EndpointTed) -> list[int]:
    # A ingestao grava tudo como texto, e o pandas pode transformar inteiro em
    # '64.0'; por isso o float antes do int.
    linhas = db.execute_query(
        f"select distinct {endpoint.coluna_ids} from {SCHEMA}.{endpoint.tabela_ids}"
    )
    ids = {int(float(valor)) for (valor,) in linhas if valor not in (None, "", "NaN")}
    return sorted(ids)


def ingerir_endpoint(
    api: ClienteTed, db: ClientPostgresDB, endpoint: EndpointTed, dt_ingest: str
) -> int:
    ids = _ids(db, endpoint)
    if not ids:
        logging.warning(f"Sem ids em {endpoint.tabela_ids} para {endpoint.tabela_api}")
        return 0

    linhas = api.get_por_ids(
        endpoint.tabela_api, endpoint.coluna_filtro, ids, endpoint.ordem
    )
    if linhas is None:
        raise RuntimeError(f"Falha na API de TED ao buscar {endpoint.tabela_api}")
    if not linhas:
        logging.warning(f"API sem linhas de {endpoint.tabela_api}; tabela mantida")
        return 0

    for linha in linhas:
        linha["dt_ingest"] = dt_ingest

    db.replace_rows(
        linhas,
        endpoint.tabela_destino,
        delete_where="true",
        delete_params=(),
        schema=SCHEMA,
    )

    logging.info(f"{len(linhas)} linhas gravadas em {SCHEMA}.{endpoint.tabela_destino}")
    return len(linhas)
