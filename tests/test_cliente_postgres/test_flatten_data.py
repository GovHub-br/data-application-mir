from airflow_lappis.plugins.cliente_postgres import ClientPostgresDB


def test_flatten_data():
    db = ClientPostgresDB(
        "fake_connection_string"
    )  # Apenas passamos um valor qualquer para conn_str

    nested_data = [
        {
            "id": 1,
            "name": "Alice",
            "address": {"city": "New York", "zip": "10001"},
            "emails": ["alice@example.com", "alice.work@example.com"],
        },
        {
            "id": 2,
            "name": "Bob",
            "address": {"city": "Los Angeles", "zip": "90001"},
            "emails": ["bob@example.com"],
        },
    ]

    expected_output = [
        {
            "id": 1,
            "name": "Alice",
            "address__city": "New York",
            "address__zip": "10001",
            "emails": "['alice@example.com', 'alice.work@example.com']",
        },
        {
            "id": 2,
            "name": "Bob",
            "address__city": "Los Angeles",
            "address__zip": "90001",
            "emails": "['bob@example.com']",
        },
    ]

    result = db._flatten_data(nested_data)

    assert result == expected_output
