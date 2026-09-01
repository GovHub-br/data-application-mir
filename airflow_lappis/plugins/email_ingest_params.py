"""Parametros compartilhados das DAGs de ingestao via e-mail.

Mantido separado de cliente_email para que o cliente IMAP continue livre de
dependencias do Airflow (facilita testes). As DAGs usam:

    from email_ingest_params import date_range_params
    ...
    params=date_range_params()
"""

from typing import Dict

from airflow.models.param import Param


def date_range_params() -> Dict[str, Param]:
    """Params opcionais de intervalo de datas para filtrar os e-mails.

    Ambos no formato YYYY-MM-DD. Sem nenhum informado, a DAG mantem o
    comportamento padrao (busca apenas o dia atual). Ver
    cliente_email.resolve_email_date_range / build_date_criteria.
    """
    return {
        "data_inicial": Param(
            default=None,
            type=["string", "null"],
            title="Data Inicial",
            description=(
                "Data inicial (inclusive) para filtrar os e-mails, no formato "
                "YYYY-MM-DD. Se vazia e 'data_final' informada, busca ate a "
                "data final. Se ambas vazias, usa apenas o dia atual."
            ),
        ),
        "data_final": Param(
            default=None,
            type=["string", "null"],
            title="Data Final",
            description=(
                "Data final (inclusive) para filtrar os e-mails, no formato "
                "YYYY-MM-DD. Se vazia e 'data_inicial' informada, busca da data "
                "inicial ate a data atual (execucao)."
            ),
        ),
    }
