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
class AdlsConfig:
    """Destino opcional do Azure Data Lake Storage Gen2."""

    enabled: bool
    account_url: str
    file_system: str
    base_directory: str
    overwrite: bool
    max_concurrency: int = 4


@dataclass(frozen=True, slots=True)
class EventHubsConfig:
    """Destino opcional de replay no Azure Event Hubs."""

    enabled: bool
    fully_qualified_namespace: str
    eventhub_name: str
    events_per_second: int
    max_batch_size: int
    starting_position: str


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
class IngestionDelayConfig:
    """Intervalos, em segundos, da simulação de chegada dos eventos."""

    late_threshold_seconds: int
    operational_min_seconds: int
    operational_max_seconds: int
    late_min_seconds: int
    late_max_seconds: int


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
    ingestion_delay: IngestionDelayConfig


@dataclass(frozen=True, slots=True)
class TransfersConfig:
    """Parâmetros das tentativas de transferência interna."""

    count: int
    min_amount: Decimal
    max_amount: Decimal
    declined_rate_overall: Decimal
    history_days: int


@dataclass(frozen=True, slots=True)
class QualityConfig:
    """Seleção de um cenário controlado de qualidade."""

    scenario: str
    rate: Decimal
    entity: str
    field: str | None


@dataclass(frozen=True, slots=True)
class BankingDataGeneratorConfig:
    """Configuração validada do gerador de dados bancários."""

    seed: int
    reference_date: date
    currency: str
    output: OutputConfig
    adls: AdlsConfig
    event_hubs: EventHubsConfig
    customers: CustomersConfig
    accounts: AccountsConfig
    merchants: MerchantsConfig
    cards: CardsConfig
    transactions: TransactionsConfig
    transfers: TransfersConfig
    quality: QualityConfig
