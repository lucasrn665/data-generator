from banking_data_generator import installation_status


def test_installation_status() -> None:
    assert installation_status() == "banking-data-generator instalado"
