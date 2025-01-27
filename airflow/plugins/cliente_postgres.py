from typing import Any, Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import execute_values
from pandas import json_normalize


class ClientPostgresDB:
    """Client for interacting with PostgreSQL database."""

    SEPARATOR = "_"

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

    @staticmethod
    def _flatten_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Flattens a list of deep dictionaries into a list of flat dictionaries.

        Args:
            data (List[Dict[str, Any]]): List of dictionaries to flatten.

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

    def create_table_if_not_exists(
        self,
        sample_data: Dict[str, Any],
        table_name: str,
        primary_key: Optional[str] = None,
        schema: str = "raw",
    ) -> None:
        """Create table dynamically based on data structure.

        Args:
            sample_data: Sample data to determine schema
            table_name: Name of table to create
            primary_key: Primary key column name
            schema: Database schema name
        """
        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")

                flattened_sample = self._flatten_data([sample_data])[0]
                column_definitions: List[str] = []

                for column, value in flattened_sample.items():
                    col_type = self._get_column_type(value)
                    column_definitions.append(f"{column} {col_type}")

                if primary_key and primary_key in flattened_sample:
                    column_definitions.append(f"PRIMARY KEY ({primary_key})")

                create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
                    {', '.join(column_definitions)}
                );"""

                try:
                    cursor.execute(create_table_query)
                except psycopg2.Error as err:
                    raise RuntimeError(
                        f"Failed to create table {schema}.{table_name}"
                    ) from err

    def insert_data(
        self,
        data: List[Dict[str, Any]],
        table_name: str,
        conflict_field: Optional[str] = None,
        primary_key: Optional[str] = None,
        schema: str = "raw",
    ) -> None:
        """Insert data into database table.

        Args:
            data: List of dictionaries to insert
            table_name: Target table name
            conflict_field: Column name for conflict resolution
            primary_key: Primary key column name
            schema: Database schema name
        """
        if not data:
            return

        self.create_table_if_not_exists(data[0], table_name, primary_key=primary_key)

        flattened_data = self._flatten_data(data)
        columns = list(flattened_data[0].keys())
        values = [tuple(item.values()) for item in flattened_data]

        sql = f"""
        INSERT INTO {schema}.{table_name} ({', '.join(columns)})
        VALUES %s
        """

        if conflict_field:
            sql += f" ON CONFLICT ({conflict_field}) DO NOTHING"

        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cursor:
                try:
                    execute_values(cursor, sql, values)
                except psycopg2.Error as err:
                    raise RuntimeError(
                        f"Failed to insert data into {table_name}"
                    ) from err

    def execute_query(self, query: str) -> List[Tuple[Any, ...]]:
        """Get all contract IDs from contratos table.

        Returns:
            List of contract IDs
        """
        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
