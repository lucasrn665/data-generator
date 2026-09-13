"""Gerador de dados bancários sintéticos."""

from banking_data_generator.version import GENERATOR_VERSION

__version__ = GENERATOR_VERSION


def installation_status() -> str:
    """Retorne uma mensagem simples para validar a instalação do pacote."""
    return "banking-data-generator instalado"
