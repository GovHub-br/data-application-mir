from typing import Dict, Any, List
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import logging
import json
from schedule_loader import get_dynamic_schedule
from cliente_email import (
    fetch_email_with_zip,
    extract_csv_from_zip,
    open_mailbox,
    resolve_email_date_range,
)
from email_ingest_params import date_range_params
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn

default_args = {
    "owner": "Mateus",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Relatorios "Notas de credito enviadas/devolvidas a partir de 2026" do Tesouro
# Gerencial, sobre o documento da NC (NC > item > celula): uma linha por celula,
# com PTRES, fonte, natureza e valor proprios. Cada celula vem duas vezes, lado
# ORIGEM e DESTINO (coluna dc), com o mesmo valor. Filtro de ano por "NC - Ano
# Emissao" ("Ano Lancamento" some do SQL: o relatorio nao tem lancamento).
COLUMN_MAPPING_NC = {
    0: "emissao_dia",
    1: "nc",
    2: "emitente_codigo",
    3: "emitente_nome",
    4: "ptres",
    5: "fonte_codigo",
    6: "fonte_nome",
    7: "natureza_codigo",
    8: "natureza_nome",
    9: "pi_codigo",
    10: "pi_nome",
    11: "descricao",
    12: "ugr_codigo",
    13: "ugr_nome",
    14: "tipo_nc",
    15: "favorecido_codigo",
    16: "favorecido_nome",
    17: "nc_transferencia",
    18: "dc",
    19: "valor_celula",
}

# relatorio: "enviadas" (emitente MIR, favorecido fora do MIR) ou "recebidas"
# (emitente fora do MIR, favorecido MIR; devolucoes e creditos recebidos)
EMAIL_CONFIGS = {
    "enviadas": {"subject": "notas_credito_mir_apos_2026", "skiprows": 3},
    "recebidas": {"subject": "notas_credito_recebidas_apos_2026", "skiprows": 3},
}

TABLE_NAME = "nc_tesouro_desde_2026"
NC_PATTERN = r"^\d{15}NC\d{6}$"

with DAG(
    dag_id="email_notas_credito_ingest_mir_pos_2026",
    default_args=default_args,
    schedule_interval=get_dynamic_schedule(
        "email_notas_credito_ingest_mir_post_2026", default="20 0 * * *"
    ),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    params=date_range_params(),
    tags=["MIR", "email", "notas_credito"],
) as dag:

    def fetch_and_ingest(**context: Dict[str, Any]) -> Dict[str, int]:
        """
        Busca as NCs (enviadas e recebidas) e grava cada anexo imediatamente.

        Cada anexo e o retrato completo do ano: substitui as linhas do mesmo
        relatorio e ano (ano do numero da NC), sem deduplicar por conteudo —
        dois itens iguais da mesma NC chegam como linhas identicas e as duas
        valem. Os anexos vem em ordem cronologica, entao o mais recente
        prevalece.
        """
        creds = json.loads(Variable.get("email_credentials"))
        params = context.get("params", {})
        data_inicial, data_final = resolve_email_date_range(
            params.get("data_inicial"), params.get("data_final")
        )

        postgres_conn_str = get_postgres_conn("postgres_mir")
        db = ClientPostgresDB(postgres_conn_str)
        total_attachments = 0
        total_records = 0

        with open_mailbox(
            creds["imap_server"], creds["email"], creds["password"]
        ) as mailbox:
            for relatorio, config in EMAIL_CONFIGS.items():
                logging.info("Iniciando o processamento das NCs %s", relatorio)
                zip_payloads: List[bytes] = fetch_email_with_zip(
                    creds["imap_server"],
                    creds["email"],
                    creds["password"],
                    creds["sender_email"],
                    config["subject"],
                    start_date=data_inicial,
                    end_date=data_final,
                    mailbox=mailbox,
                )

                if not zip_payloads:
                    logging.warning("Nenhum e-mail encontrado para NCs %s", relatorio)
                    continue

                logging.info(
                    "NCs %s: %s anexos encontrados", relatorio, len(zip_payloads)
                )

                for idx, payload in enumerate(zip_payloads, 1):
                    df = extract_csv_from_zip(
                        payload,
                        COLUMN_MAPPING_NC,
                        config["skiprows"],
                        sep="\t",
                        dtype=str,
                    )
                    if df is None or df.empty:
                        logging.warning(
                            "NCs %s anexo %s ignorado (CSV inválido/vazio).",
                            relatorio,
                            idx,
                        )
                        continue

                    # Mapeamento por posicao: com outro numero de colunas os
                    # campos cairiam deslocados
                    if len(df.columns) != len(COLUMN_MAPPING_NC):
                        logging.error(
                            "NCs %s anexo %s ignorado: %s colunas, esperado %s. "
                            "O layout do relatorio mudou?",
                            relatorio,
                            idx,
                            len(df.columns),
                            len(COLUMN_MAPPING_NC),
                        )
                        continue

                    df = df[df["nc"].str.match(NC_PATTERN, na=False)]
                    if df.empty:
                        logging.warning(
                            "NCs %s anexo %s sem linhas de NC.", relatorio, idx
                        )
                        continue

                    df = df.assign(
                        relatorio=relatorio, dt_ingest=datetime.now().isoformat()
                    )
                    anos = sorted(df["nc"].str[11:15].unique().tolist())
                    data = df.to_dict(orient="records")

                    db.replace_rows(
                        data,
                        TABLE_NAME,
                        "relatorio = %s AND substr(nc, 12, 4) = ANY(%s)",
                        (relatorio, anos),
                        schema="siafi",
                    )
                    total_attachments += 1
                    total_records += len(data)
                    logging.info(
                        "NCs %s anexo %s (anos %s): %s registros gravados",
                        relatorio,
                        idx,
                        anos,
                        len(data),
                    )
                    del df, data

        logging.info("Total: %s anexos, %s registros", total_attachments, total_records)
        return {"attachments": total_attachments, "records": total_records}

    PythonOperator(
        task_id="fetch_and_ingest",
        python_callable=fetch_and_ingest,
    )
