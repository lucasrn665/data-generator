"""Carregamento e validação da configuração YAML."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Never

import yaml

from banking_data_generator.config.models import (
    AccountsConfig,
    BankingDataGeneratorConfig,
    CardsConfig,
    CustomersConfig,
    DailyPurchaseLimitConfig,
    IngestionDelayConfig,
    InitialBalanceConfig,
    MerchantsConfig,
    OutputConfig,
    QualityConfig,
    TransactionsConfig,
    TransfersConfig,
)

_ROOT_FIELDS = {
    "seed",
    "reference_date",
    "currency",
    "output",
    "customers",
    "accounts",
    "merchants",
    "cards",
    "transactions",
    "transfers",
    "quality",
}
_OUTPUT_FIELDS = {"directory", "format"}
_CUSTOMERS_FIELDS = {"count"}
_ACCOUNTS_FIELDS = {"min_per_customer", "max_per_customer", "initial_balance"}
_INITIAL_BALANCE_FIELDS = {"min", "max"}
_MERCHANTS_FIELDS = {"count"}
_CARDS_FIELDS = {"per_account", "daily_purchase_limit", "initially_blocked_rate"}
_DAILY_PURCHASE_LIMIT_FIELDS = {"min", "max"}
_TRANSACTIONS_FIELDS = {
    "count",
    "purchase_amount",
    "history_days",
    "fraud_rate_overall",
    "declined_rate_overall",
    "reversal_rate_of_approved",
    "late_event_rate_overall",
    "ingestion_delay",
}
_INGESTION_DELAY_FIELDS = {
    "late_threshold_seconds",
    "operational_min_seconds",
    "operational_max_seconds",
    "late_min_seconds",
    "late_max_seconds",
}
_PURCHASE_AMOUNT_FIELDS = {"min", "max"}
_TRANSFERS_FIELDS = {
    "count",
    "min_amount",
    "max_amount",
    "declined_rate_overall",
    "history_days",
}
_QUALITY_FIELDS = {"scenario", "rate", "entity", "field"}
_QUALITY_SCENARIOS = {
    "valid",
    "duplicate_exact",
    "duplicate_conflicting",
    "required_null",
    "orphan_foreign_key",
    "late_event",
    "schema_additive_column",
    "schema_missing_column",
    "schema_renamed_column",
    "schema_incompatible_value",
    "schema_unknown_enum",
}
_SCHEMA_QUALITY_SCENARIOS = {
    "schema_additive_column",
    "schema_missing_column",
    "schema_renamed_column",
    "schema_incompatible_value",
    "schema_unknown_enum",
}
_QUALITY_ENTITIES = {
    "customers",
    "addresses",
    "accounts",
    "cards",
    "merchants",
    "transactions",
}
_CONFLICTING_FIELDS = {
    "customers": {"synthetic_name"},
    "addresses": {"street", "neighborhood", "city", "state", "country"},
    "merchants": {"synthetic_name", "city", "state", "country"},
}
_REQUIRED_NULL_FIELDS = {
    "customers": {"synthetic_name", "synthetic_email"},
    "addresses": {"street", "neighborhood", "city", "state", "country"},
    "merchants": {"synthetic_name", "city", "state", "country"},
}
_ORPHAN_FIELDS = {
    "addresses": {"customer_id"},
    "accounts": {"customer_id"},
    "cards": {"account_id"},
    "transactions": {"merchant_id"},
}
_ZERO = Decimal("0")
_ONE = Decimal("1")


class ConfigError(ValueError):
    """Erro encontrado no contrato da configuração."""


def load_config(path: str | Path) -> BankingDataGeneratorConfig:
    """Carregue e valide um arquivo YAML sem construir objetos arbitrários."""
    config_path = Path(path)
    try:
        contents = config_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(
            f"Não foi possível ler a configuração '{config_path}': {error}"
        ) from error

    try:
        raw = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise ConfigError(f"YAML inválido em '{config_path}': {error}") from error

    root = _mapping(raw, "config")
    _validate_fields(root, _ROOT_FIELDS, "config")

    output = _mapping(root["output"], "output")
    customers = _mapping(root["customers"], "customers")
    accounts = _mapping(root["accounts"], "accounts")
    merchants = _mapping(root["merchants"], "merchants")
    cards = _mapping(root["cards"], "cards")
    transactions = _mapping(root["transactions"], "transactions")
    transfers = _mapping(root["transfers"], "transfers")
    quality = _mapping(root["quality"], "quality")

    _validate_fields(output, _OUTPUT_FIELDS, "output")
    _validate_fields(customers, _CUSTOMERS_FIELDS, "customers")
    _validate_fields(accounts, _ACCOUNTS_FIELDS, "accounts")
    initial_balance = _mapping(accounts["initial_balance"], "accounts.initial_balance")
    _validate_fields(
        initial_balance,
        _INITIAL_BALANCE_FIELDS,
        "accounts.initial_balance",
    )
    _validate_fields(transactions, _TRANSACTIONS_FIELDS, "transactions")
    _validate_fields(transfers, _TRANSFERS_FIELDS, "transfers")
    _validate_fields(quality, _QUALITY_FIELDS, "quality")
    purchase_amount = _mapping(
        transactions["purchase_amount"], "transactions.purchase_amount"
    )
    ingestion_delay = _mapping(
        transactions["ingestion_delay"], "transactions.ingestion_delay"
    )
    _validate_fields(
        ingestion_delay, _INGESTION_DELAY_FIELDS, "transactions.ingestion_delay"
    )
    _validate_fields(
        purchase_amount, _PURCHASE_AMOUNT_FIELDS, "transactions.purchase_amount"
    )
    _validate_fields(merchants, _MERCHANTS_FIELDS, "merchants")
    _validate_fields(cards, _CARDS_FIELDS, "cards")
    daily_limit = _mapping(cards["daily_purchase_limit"], "cards.daily_purchase_limit")
    _validate_fields(
        daily_limit, _DAILY_PURCHASE_LIMIT_FIELDS, "cards.daily_purchase_limit"
    )

    minimum_balance = _money(initial_balance["min"], "accounts.initial_balance.min")
    maximum_balance = _money(initial_balance["max"], "accounts.initial_balance.max")
    _validate_order(
        minimum_balance,
        maximum_balance,
        "accounts.initial_balance.min",
        "accounts.initial_balance.max",
    )
    minimum_daily_limit = _money(daily_limit["min"], "cards.daily_purchase_limit.min")
    maximum_daily_limit = _money(daily_limit["max"], "cards.daily_purchase_limit.max")
    _validate_order(
        minimum_daily_limit,
        maximum_daily_limit,
        "cards.daily_purchase_limit.min",
        "cards.daily_purchase_limit.max",
    )
    if minimum_daily_limit <= _ZERO:
        _fail("cards.daily_purchase_limit.min", "deve ser maior que 0.00")
    minimum_purchase = _money(
        purchase_amount["min"], "transactions.purchase_amount.min"
    )
    maximum_purchase = _money(
        purchase_amount["max"], "transactions.purchase_amount.max"
    )
    _validate_order(
        minimum_purchase,
        maximum_purchase,
        "transactions.purchase_amount.min",
        "transactions.purchase_amount.max",
    )
    if minimum_purchase <= _ZERO:
        _fail("transactions.purchase_amount.min", "deve ser maior que 0.00")
    minimum_transfer = _money(transfers["min_amount"], "transfers.min_amount")
    maximum_transfer = _money(transfers["max_amount"], "transfers.max_amount")
    _validate_order(
        minimum_transfer,
        maximum_transfer,
        "transfers.min_amount",
        "transfers.max_amount",
    )
    if minimum_transfer <= _ZERO:
        _fail("transfers.min_amount", "deve ser maior que 0.00")
    quality_scenario = _choice(
        quality["scenario"], "quality.scenario", _QUALITY_SCENARIOS
    )
    quality_entity = _choice(quality["entity"], "quality.entity", _QUALITY_ENTITIES)
    quality_field = _optional_string(quality["field"], "quality.field")
    _validate_quality_target(quality_scenario, quality_entity, quality_field)
    if (
        quality_scenario in _SCHEMA_QUALITY_SCENARIOS
        and quality_entity != "transactions"
    ):
        _fail("quality.entity", "deve ser 'transactions' para cenários de schema")
    delay_values = {
        name: _non_negative_int(value, f"transactions.ingestion_delay.{name}")
        for name, value in ingestion_delay.items()
    }
    _validate_order(
        delay_values["operational_min_seconds"],
        delay_values["operational_max_seconds"],
        "transactions.ingestion_delay.operational_min_seconds",
        "transactions.ingestion_delay.operational_max_seconds",
    )
    _validate_order(
        delay_values["late_min_seconds"],
        delay_values["late_max_seconds"],
        "transactions.ingestion_delay.late_min_seconds",
        "transactions.ingestion_delay.late_max_seconds",
    )
    if delay_values["operational_max_seconds"] > delay_values["late_threshold_seconds"]:
        _fail(
            "transactions.ingestion_delay.operational_max_seconds",
            "deve ser menor ou igual ao limite tardio",
        )
    if delay_values["late_min_seconds"] <= delay_values["late_threshold_seconds"]:
        _fail(
            "transactions.ingestion_delay.late_min_seconds",
            "deve ser maior que o limite tardio",
        )

    minimum_accounts = _positive_int(
        accounts["min_per_customer"], "accounts.min_per_customer"
    )
    maximum_accounts = _non_negative_int(
        accounts["max_per_customer"], "accounts.max_per_customer"
    )
    _validate_order(
        minimum_accounts,
        maximum_accounts,
        "accounts.min_per_customer",
        "accounts.max_per_customer",
    )

    return BankingDataGeneratorConfig(
        seed=_non_negative_int(root["seed"], "seed"),
        reference_date=_date(root["reference_date"], "reference_date"),
        currency=_choice(root["currency"], "currency", {"BRL"}),
        output=OutputConfig(
            directory=Path(_non_empty_string(output["directory"], "output.directory")),
            format=_choice(output["format"], "output.format", {"csv"}),
        ),
        customers=CustomersConfig(
            count=_non_negative_int(customers["count"], "customers.count")
        ),
        accounts=AccountsConfig(
            min_per_customer=minimum_accounts,
            max_per_customer=maximum_accounts,
            initial_balance=InitialBalanceConfig(
                min=minimum_balance,
                max=maximum_balance,
            ),
        ),
        merchants=MerchantsConfig(
            count=_non_negative_int(merchants["count"], "merchants.count")
        ),
        cards=CardsConfig(
            per_account=_positive_int(cards["per_account"], "cards.per_account"),
            daily_purchase_limit=DailyPurchaseLimitConfig(
                min=minimum_daily_limit,
                max=maximum_daily_limit,
            ),
            initially_blocked_rate=_rate(
                cards["initially_blocked_rate"], "cards.initially_blocked_rate"
            ),
        ),
        transactions=TransactionsConfig(
            count=_non_negative_int(transactions["count"], "transactions.count"),
            purchase_amount=InitialBalanceConfig(
                min=minimum_purchase, max=maximum_purchase
            ),
            history_days=_positive_int(
                transactions["history_days"], "transactions.history_days"
            ),
            fraud_rate_overall=_rate(
                transactions["fraud_rate_overall"],
                "transactions.fraud_rate_overall",
            ),
            declined_rate_overall=_rate(
                transactions["declined_rate_overall"],
                "transactions.declined_rate_overall",
            ),
            reversal_rate_of_approved=_rate(
                transactions["reversal_rate_of_approved"],
                "transactions.reversal_rate_of_approved",
            ),
            late_event_rate_overall=_rate(
                transactions["late_event_rate_overall"],
                "transactions.late_event_rate_overall",
            ),
            ingestion_delay=IngestionDelayConfig(**delay_values),
        ),
        transfers=TransfersConfig(
            count=_non_negative_int(transfers["count"], "transfers.count"),
            min_amount=minimum_transfer,
            max_amount=maximum_transfer,
            declined_rate_overall=_rate(
                transfers["declined_rate_overall"],
                "transfers.declined_rate_overall",
            ),
            history_days=_positive_int(
                transfers["history_days"], "transfers.history_days"
            ),
        ),
        quality=QualityConfig(
            scenario=quality_scenario,
            rate=_rate(quality["rate"], "quality.rate"),
            entity=quality_entity,
            field=quality_field,
        ),
    )


def _validate_quality_target(scenario: str, entity: str, field: str | None) -> None:
    allowed: dict[str, dict[str, set[str]]] = {
        "duplicate_conflicting": _CONFLICTING_FIELDS,
        "required_null": _REQUIRED_NULL_FIELDS,
        "orphan_foreign_key": _ORPHAN_FIELDS,
    }
    if scenario not in allowed:
        return
    if field is None or field not in allowed[scenario].get(entity, set()):
        _fail(
            "quality",
            f"combinação de entidade e campo não permitida para '{scenario}'",
        )


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "deve ser um objeto")
    return value


def _validate_fields(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    unknown = sorted(actual - expected, key=str)
    if unknown:
        names = ", ".join(str(item) for item in unknown)
        _fail(path, f"propriedades desconhecidas: {names}")
    missing = sorted(expected - actual)
    if missing:
        _fail(path, f"propriedades obrigatórias ausentes: {', '.join(missing)}")


def _non_negative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "deve ser um número inteiro")
    if value < 0:
        _fail(path, "deve ser maior ou igual a 0")
    return value


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "deve ser um número inteiro")
    if value < 1:
        _fail(path, "deve ser maior ou igual a 1")
    return value


def _money(value: Any, path: str) -> Decimal:
    if not isinstance(value, str):
        _fail(path, "deve ser uma string monetária com duas casas decimais")
    whole, separator, fraction = value.partition(".")
    if (
        separator != "."
        or len(fraction) != 2
        or not whole.isdigit()
        or not fraction.isdigit()
    ):
        _fail(path, "deve ser uma string monetária não negativa, como '100.00'")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        _fail(path, "contém um valor monetário inválido")
    if amount < _ZERO:
        _fail(path, "deve ser maior ou igual a 0.00")
    return amount


def _rate(value: Any, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        _fail(path, "deve ser uma taxa numérica entre 0 e 1")
    try:
        rate = Decimal(str(value))
    except InvalidOperation:
        _fail(path, "deve ser uma taxa numérica entre 0 e 1")
    if not rate.is_finite() or not _ZERO <= rate <= _ONE:
        _fail(path, "deve estar entre 0 e 1, inclusive")
    return rate


def _date(value: Any, path: str) -> date:
    if not isinstance(value, str):
        _fail(path, "deve ser uma data ISO no formato YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(path, "deve ser uma data ISO válida no formato YYYY-MM-DD")


def _non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "deve ser uma string não vazia")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, path)


def _choice(value: Any, path: str, choices: set[str]) -> str:
    text = _non_empty_string(value, path)
    if text not in choices:
        _fail(path, f"deve ser um de: {', '.join(sorted(choices))}")
    return text


def _validate_order(
    minimum: int | Decimal,
    maximum: int | Decimal,
    minimum_path: str,
    maximum_path: str,
) -> None:
    if minimum > maximum:
        _fail(minimum_path, f"deve ser menor ou igual a {maximum_path}")


def _fail(path: str, message: str) -> Never:
    raise ConfigError(f"Configuração inválida em '{path}': {message}.")
