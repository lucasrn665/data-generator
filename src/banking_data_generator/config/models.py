"""Modelos tipados e imutáveis da configuração."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OutputConfig:
    """Configuração do destino batch."""

    directory: Path
    format: str


@dataclass(frozen=True, slots=True)
class CustomersConfig:
    """Parâmetros para a futura geração de clientes."""

    count: int


@dataclass(frozen=True, slots=True)
class InitialBalanceConfig:
    """Intervalo permitido para o saldo inicial em unidades monetárias."""

    min: Decimal
    max: Decimal


@dataclass(frozen=True, slots=True)
class AccountsConfig:
    """Parâmetros para a futura geração de contas."""

    min_per_customer: int
    max_per_customer: int
    initial_balance: InitialBalanceConfig


@dataclass(frozen=True, slots=True)
class MerchantsConfig:
    """Parâmetros da geração de estabelecimentos sintéticos."""

    count: int


@dataclass(frozen=True, slots=True)
class DailyPurchaseLimitConfig:
    """Intervalo permitido para o limite diário dos cartões."""

    min: Decimal
    max: Decimal


@dataclass(frozen=True, slots=True)
class CardsConfig:
    """Parâmetros da geração de cartões de débito sintéticos."""

    per_account: int
    daily_purchase_limit: DailyPurchaseLimitConfig
    initially_blocked_rate: Decimal


@dataclass(frozen=True, slots=True)
class TransactionsConfig:
    """Parâmetros para a futura geração de transações."""

    count: int
    purchase_amount: InitialBalanceConfig
    history_days: int
    fraud_rate_overall: Decimal
    declined_rate_overall: Decimal
    reversal_rate_of_approved: Decimal
    late_event_rate_overall: Decimal


@dataclass(frozen=True, slots=True)
class TransfersConfig:
    """Parâmetros das tentativas de transferência interna."""

    count: int
    min_amount: Decimal
    max_amount: Decimal
    declined_rate_overall: Decimal
    history_days: int


@dataclass(frozen=True, slots=True)
class BankingDataGeneratorConfig:
    """Configuração validada do gerador de dados bancários."""

    seed: int
    reference_date: date
    currency: str
    output: OutputConfig
    customers: CustomersConfig
    accounts: AccountsConfig
    merchants: MerchantsConfig
    cards: CardsConfig
    transactions: TransactionsConfig
    transfers: TransfersConfig
