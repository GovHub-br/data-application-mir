import zipfile
import io
import pandas as pd
from airflow_lappis.plugins.cliente_email import extract_csv_from_zip


def test_extract_csv_from_zip_success():
    # Cria um arquivo ZIP em memória com um CSV dentro
    csv_data = """ignore1\nignore2\nignore3\nignore4\nignore5\n1,2,3\n4,5,6\n"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("test.csv", csv_data)
    zip_buffer.seek(0)

    # Executa a função
    column_mapping = {0: "col1", 1: "col2", 2: "col3"}
    result = extract_csv_from_zip(zip_buffer.getvalue(), column_mapping)

    # Verifica o resultado
    expected = pd.DataFrame({"col1": [1, 4], "col2": [2, 5], "col3": [3, 6]})
    pd.testing.assert_frame_equal(result, expected)


def test_extract_csv_from_zip_no_csv():
    # Cria um arquivo ZIP em memória sem CSV
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("test.txt", "Hello, World!")
    zip_buffer.seek(0)

    # Executa a função
    column_mapping = {0: "col1", 1: "col2", 2: "col3"}
    result = extract_csv_from_zip(zip_buffer.getvalue(), column_mapping)

    # Verifica se o resultado é None
    assert result is None
