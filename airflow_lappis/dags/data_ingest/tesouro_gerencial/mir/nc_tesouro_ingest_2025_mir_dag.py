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

# Relatorios "Notas de credito enviadas/devolvidas ate 2025" do Tesouro
# Gerencial. So atributos do lancamento (WF_LANCAMENTO): atributos "NC - ..."
# (valor linha, evento, natureza da NC) ligam pela NC inteira e cruzam cada
# linha da NC com todos os lancamentos. Filtros: Item Informacao 15-18
# (provisao/destaque recebido/concedido) e UG Executora = UGs do MIR, para
# contar so o lado do MIR. O valor e o movimento liquido, com sinal do ponto de
# vista do MIR (descentralizacao +, anulacao/devolucao -).
COLUMN_MAPPING = {
    0: "programa_governo",
    1: "programa_governo_descricao",
    2: "acao_governo",
    3: "acao_governo_descricao",
    4: "nc",
    5: "nc_transferencia",
    6: "fonte_recursos",
    7: "fonte_recursos_descricao",
    8: "ptres",
    9: "ug_responsavel",
    10: "ug_responsavel_descricao",
    11: "natureza_despesa",
    12: "natureza_despesa_descricao",
    13: "plano_interno",
    14: "plano_interno_descricao",
    15: "favorecido_doc",
    16: "favorecido_doc_descricao",
    17: "favorecido_municipio",
    18: "favorecido_municipio_descricao",
    19: "movimento_liquido_moeda_origem",
}

# relatorio: "enviadas" (emitente MIR, favorecido fora do MIR) ou "recebidas"
# (emitente fora do MIR, favorecido MIR; devolucoes e creditos recebidos)
EMAIL_CONFIGS = {
    "enviadas": {"subject": "notas_credito_mir_ate_2025", "skiprows": 6},
    "recebidas": {"subject": "notas_credito_recebidas_ate_2025", "skiprows": 6},
}

TABLE_NAME = "nc_tesouro_ate_2025"
NC_PATTERN = r"^\d{15}NC\d{6}$"

with DAG(
    dag_id="email_notas_credito_ingest_mir_ate_2025",
    default_args=default_args,
    schedule_interval=get_dynamic_schedule(
        "email_notas_credito_ingest_mir_ate_2025", default="15 0 * * *"
    ),
    start_date=datetime(2023, 12, 1),
    catchup=False,
    params=date_range_params(),
    tags=["MIR", "SIAFI", "notas_credito"],
) as dag:

    def fetch_and_ingest(**context: Dict[str, Any]) -> Dict[str, int]:
        """
        Busca as NCs (enviadas e recebidas) e grava cada anexo imediatamente.

        Cada anexo e o retrato completo dos anos que traz: substitui as linhas
        do mesmo relatorio e ano (ano do numero da NC). Os anexos vem em ordem
        cronologica, entao o mais recente prevalece.

        As duas buscas reusam a MESMA sessão IMAP (open_mailbox) em vez de
        logar duas vezes — dois logins em sequência já foram o suficiente
        para estourar o [OVERQUOTA] do provedor.
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
                logging.info(f"Iniciando o processamento das NCs {relatorio}")
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
                    logging.warning(f"Nenhum e-mail encontrado para NCs {relatorio}")
                    continue

                logging.info(
                    "NCs %s: %s anexos encontrados", relatorio, len(zip_payloads)
                )

                for idx, payload in enumerate(zip_payloads, 1):
                    df = extract_csv_from_zip(
                        payload, COLUMN_MAPPING, config["skiprows"], dtype=str
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
                    if len(df.columns) != len(COLUMN_MAPPING):
                        logging.error(
                            "NCs %s anexo %s ignorado: %s colunas, esperado %s. "
                            "O layout do relatorio mudou?",
                            relatorio,
                            idx,
                            len(df.columns),
                            len(COLUMN_MAPPING),
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
        provide_context=True,
    )
