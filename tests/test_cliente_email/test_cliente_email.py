import pytest
import pandas as pd
import logging
from airflow_lappis.plugins.cliente_email import (
    format_csv,
)

logging.basicConfig(level=logging.INFO)


def test_format_csv_success():
    csv_data = """ignore1\nignore2\nignore3\nignore4\nignore5\n1,2,3\n4,5,6\n"""
    column_mapping = {0: "A", 1: "B", 2: "C"}

    expected_data = {"A": [1, 4], "B": [2, 5], "C": [3, 6]}
    expected_df = pd.DataFrame(expected_data)

    df = format_csv(csv_data, column_mapping)

    pd.testing.assert_frame_equal(df, expected_df)


def test_format_csv_invalid_data():
    csv_data = """ignore1\nignore2\nignore3\nignore4\nignore5\na,b,c\nd,e,f\n"""
    column_mapping = {0: "X", 1: "Y", 2: "Z"}

    df = format_csv(csv_data, column_mapping)

    assert df.iloc[0]["X"] == "a"
    assert df.iloc[1]["Y"] == "e"


def test_format_csv_empty_data():
    csv_data = """ignore1\nignore2\nignore3\nignore4\nignore5\n"""
    column_mapping = {0: "A", 1: "B"}

    try:
        df = format_csv(csv_data, column_mapping)
        assert df.empty
    except ValueError as e:
        assert "No columns to parse from file" in str(e)


def test_format_csv_exception():
    csv_data = None  # CSV inválido
    column_mapping = {0: "A", 1: "B"}

    with pytest.raises(ValueError, match="Erro ao formatar CSV"):
        format_csv(csv_data, column_mapping)
