"""Contrato público para a configuração do gerador."""

from banking_data_generator.config.loader import ConfigError, load_config
from banking_data_generator.config.models import (
    AccountsConfig,
    BankingDataGeneratorConfig,
    CustomersConfig,
    InitialBalanceConfig,
    OutputConfig,
    TransactionsConfig,
)

__all__ = [
    "AccountsConfig",
    "BankingDataGeneratorConfig",
    "ConfigError",
    "CustomersConfig",
    "InitialBalanceConfig",
    "OutputConfig",
    "TransactionsConfig",
    "load_config",
]
