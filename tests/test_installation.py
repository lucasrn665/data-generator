from banking_data_generator import __version__, installation_status
from banking_data_generator.version import GENERATOR_VERSION


def test_installation_status() -> None:
    assert installation_status() == "banking-data-generator instalado"
    assert __version__ == GENERATOR_VERSION
