import logging
from typing import Any, Dict, List, Optional, Tuple
import psycopg2
from pandas import json_normalize
import pandas as pd
import io
import psycopg2.extras


class ClientPostgresDB:
    """Client for interacting with PostgreSQL database."""

    SEPARATOR = "__"
    TYPE_MAP = {int: "BIGINT", float: "NUMERIC", bool: "BOOLEAN"}

    @staticmethod
    def _get_column_type(value: Any) -> str:
        """
        Determine PostgreSQL column type from Python value.

        Args:
            value: Python value to analyze

        Returns:
            PostgreSQL column type as string
        """
        return ClientPostgresDB.TYPE_MAP.get(type(value), "TEXT")

    def _flatten_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Flatten nested JSON data.

        Args:
            data (List[Dict[str, Any]]): List of nested dictionaries.

        Returns:
            List[Dict[str, Any]]: List of flat dictionaries.
        """
        return list(
            map(
                lambda d: {
                    str(k): v if type(v) is not list else str(v) for k, v in d.items()
                },
                json_normalize(data, sep=ClientPostgresDB.SEPARATOR).to_dict(
                    orient="records"
                ),
            )
        )

    def __init__(self, conn_str: str) -> None:
        self.conn_str = conn_str
        logging.info(
            f"[cliente_postgres.py] Initialized ClientPostgresDB with conn_str: "
            f"{conn_str}"
        )

    def create_table_if_not_exists(
        self,
        sample_data: Dict[str, Any],
        table_name: str,
        primary_key: Optional[List[str]] = None,
        schema: str = "raw",
    ) -> None:
        """Create table dynamically based on data structure.

        Args:
            sample_data: Sample data to determine schema
            table_name: Name of table to create
            primary_key: List of primary key column names
            schema: Database schema name
        """
        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
                logging.info(f"[cliente_postgres.py] Schema {schema} ensured to exist")

                flattened_sample = self._flatten_data([sample_data])[0]
                column_definitions: List[str] = []

                for column in flattened_sample.keys():
                    column_definitions.append(f"{column} TEXT")

                if primary_key:
                    pk_str = ", ".join(primary_key)
                    column_definitions.append(f"PRIMARY KEY ({pk_str})")

                create_table_query = (
                    f"CREATE TABLE IF NOT EXISTS {schema}.{table_name} ("
                    f"{', '.join(column_definitions)});"
                )

                try:
                    cursor.execute(create_table_query)
                    logging.info(
                        f"[cliente_postgres.py] Table {schema}.{table_name} created "
                        f"or already exists"
                    )
                except psycopg2.Error as err:
                    logging.error(
                        f"[cliente_postgres.py] Failed to create table {schema}."
                        f"{table_name}. Error: {str(err)}"
                    )
                    raise RuntimeError(
                        f"Failed to create table {schema}.{table_name}"
                    ) from err

    def insert_data(
        self,
        data: List[Dict[str, Any]],
        table_name: str,
        conflict_fields: Optional[List[str]] = None,
        primary_key: Optional[List[str]] = None,
        schema: str = "raw",
    ) -> None:
        """Insert data into database table.

        Args:
            data: List of dictionaries to insert
            table_name: Target table name
            conflict_fields: List of column names for conflict resolution
            primary_key: List of primary key column names
            schema: Database schema name
        """
        if not data:
            logging.warning(
                f"[cliente_postgres.py] No data to insert into {schema}.{table_name}"
            )
            return

        self.create_table_if_not_exists(
            data[0], table_name, primary_key=primary_key, schema=schema
        )

        flattened_data = self._flatten_data(data)
        columns = list(flattened_data[0].keys())
        values = [tuple(item.values()) for item in flattened_data]

        sql = f"INSERT INTO {schema}.{table_name} ({', '.join(columns)}) VALUES %s"

        if conflict_fields:
            conflict_str = ", ".join(conflict_fields)
            update_str = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns])
            sql += f" ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str}"

        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cursor:
                try:
                    psycopg2.extras.execute_values(cursor, sql, values)
                    conn.commit()
                    logging.info(
                        f"[cliente_postgres.py] Inserted data into {schema}."
                        f"{table_name}"
                    )
                except psycopg2.Error as err:
                    logging.error(
                        f"[cliente_postgres.py] Failed to insert data into {schema}."
                        f"{table_name}. Error: {str(err)}"
                    )
                    raise RuntimeError(
                        f"Failed to insert data into {schema}.{table_name}"
                    ) from err

    def execute_query(self, query: str) -> List[Tuple[Any, ...]]:
        """Execute a query and return the results.

        Args:
            query: SQL query to execute

        Returns:
            List of tuples containing the query results
        """
        logging.info(f"[cliente_postgres.py] Executing query: {query}")
        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                logging.info(
                    f"[cliente_postgres.py] Query executed successfully, fetched "
                    f"{len(results)} rows"
                )
                return results

    def get_contratos_ids(self) -> List[int]:
        """Extrai todos os IDs de contratos da tabela contratos."""
        query = "SELECT id FROM raw.contratos"

        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                contratos_ids = [row[0] for row in cursor.fetchall()]
                return contratos_ids

    def drop_table_if_exists(self, table_name: str, schema: str = "raw") -> None:
        """Remove a tabela se ela existir."""
        conn = psycopg2.connect(self.conn_str)
        cursor = conn.cursor()
        drop_table_query = f"DROP TABLE IF EXISTS {schema}.{table_name};"
        try:
            cursor.execute(drop_table_query)
            conn.commit()
            print(f"Tabela {schema}.{table_name} removida com sucesso.")
        except Exception as e:
            print(f"Erro ao remover a tabela {schema}.{table_name}: {e}")
        finally:
            cursor.close()
            conn.close()

    def insert_csv_data(
        self, csv_data: str, table_name: str, schema: str = "raw"
    ) -> None:
        """
        Insere dados de um CSV no banco de dados, garantindo que a tabela seja criada.
        Se a tabela existir, ela será removida antes da inserção dos novos dados.

        Args:
            csv_data (str): Dados do CSV como string.
            table_name (str): Nome da tabela de destino.
            schema (str): Nome do schema do banco (padrão: "raw").
        """
        # Converte o CSV para DataFrame
        df = pd.read_csv(io.StringIO(csv_data))

        # Converte o DataFrame para lista de dicionários
        data = df.to_dict(orient="records")

        # Remove a tabela existente
        self.drop_table_if_exists(table_name, schema)

        # Insere os novos dados
        self.insert_data(data, table_name, primary_key=None, schema=schema)
