"""Carregamento e validação da configuração YAML."""

import os
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PureWindowsPath
from typing import Any, Never

import yaml

from banking_data_generator.config.models import (
    AccountsConfig,
    AdlsConfig,
    BankingDataGeneratorConfig,
    CardsConfig,
    CustomersConfig,
    DailyPurchaseLimitConfig,
    EventHubsConfig,
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
    "adls",
    "event_hubs",
    "customers",
    "accounts",
    "merchants",
    "cards",
    "transactions",
    "transfers",
    "quality",
}
_OUTPUT_FIELDS = {"directory", "format"}
_ADLS_FIELDS = {
    "enabled",
    "account_url",
    "file_system",
    "base_directory",
    "overwrite",
    "max_concurrency",
}
_EVENT_HUBS_FIELDS = {
    "enabled",
    "fully_qualified_namespace",
    "eventhub_name",
    "events_per_second",
    "max_batch_size",
    "starting_position",
}
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
    "mixed",
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
    _apply_adls_environment(root)
    _apply_event_hubs_environment(root)
    _validate_fields(root, _ROOT_FIELDS, "config")

    output = _mapping(root["output"], "output")
    adls = _mapping(root["adls"], "adls")
    event_hubs = _mapping(root["event_hubs"], "event_hubs")
    customers = _mapping(root["customers"], "customers")
    accounts = _mapping(root["accounts"], "accounts")
    merchants = _mapping(root["merchants"], "merchants")
    cards = _mapping(root["cards"], "cards")
    transactions = _mapping(root["transactions"], "transactions")
    transfers = _mapping(root["transfers"], "transfers")
    quality = _mapping(root["quality"], "quality")

    _validate_fields(output, _OUTPUT_FIELDS, "output")
    _validate_fields(adls, _ADLS_FIELDS, "adls")
    _validate_fields(event_hubs, _EVENT_HUBS_FIELDS, "event_hubs")
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
    adls_url = _non_empty_string(adls["account_url"], "adls.account_url")
    adls_filesystem = _adls_name(adls["file_system"], "adls.file_system")
    adls_base = _relative_remote_path(adls["base_directory"], "adls.base_directory")
    adls_max_concurrency = _bounded_int(
        adls["max_concurrency"], "adls.max_concurrency", 1, 16
    )
    if not adls_url.startswith("https://") or not adls_url.removesuffix("/").endswith(
        ".dfs.core.windows.net"
    ):
        _fail("adls.account_url", "deve usar HTTPS e host .dfs.core.windows.net")
    event_namespace = _non_empty_string(
        event_hubs["fully_qualified_namespace"], "event_hubs.fully_qualified_namespace"
    )
    if not event_namespace.removesuffix("/").endswith(".servicebus.windows.net"):
        _fail(
            "event_hubs.fully_qualified_namespace",
            "deve terminar em .servicebus.windows.net",
        )
    eventhub_name = _non_empty_string(
        event_hubs["eventhub_name"], "event_hubs.eventhub_name"
    )
    events_per_second = _non_negative_int(
        event_hubs["events_per_second"], "event_hubs.events_per_second"
    )
    max_batch_size = _positive_int(
        event_hubs["max_batch_size"], "event_hubs.max_batch_size"
    )
    starting_position = _choice(
        event_hubs["starting_position"], "event_hubs.starting_position", {"beginning"}
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
        adls=AdlsConfig(
            enabled=_bool(adls["enabled"], "adls.enabled"),
            account_url=adls_url.removesuffix("/"),
            file_system=adls_filesystem,
            base_directory=adls_base,
            overwrite=_bool(adls["overwrite"], "adls.overwrite"),
            max_concurrency=adls_max_concurrency,
        ),
        event_hubs=EventHubsConfig(
            enabled=_bool(event_hubs["enabled"], "event_hubs.enabled"),
            fully_qualified_namespace=event_namespace.removesuffix("/"),
            eventhub_name=eventhub_name,
            events_per_second=events_per_second,
            max_batch_size=max_batch_size,
            starting_position=starting_position,
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


def _bounded_int(value: Any, path: str, minimum: int, maximum: int) -> int:
    result = _positive_int(value, path)
    if result > maximum:
        _fail(path, f"deve estar entre {minimum} e {maximum}")
    return result


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


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "deve ser booleano")
    return value


def _relative_remote_path(value: Any, path: str) -> str:
    text = _non_empty_string(value, path)
    pure = Path(text)
    if (
        pure.is_absolute()
        or PureWindowsPath(text).is_absolute()
        or ".." in pure.parts
        or text in {".", ".."}
        or any(not part for part in text.replace("\\", "/").split("/"))
    ):
        _fail(path, "deve ser um caminho relativo sem '..' ou segmentos vazios")
    return text.strip("/")


def _adls_name(value: Any, path: str) -> str:
    text = _non_empty_string(value, path)
    if "/" in text or "\\" in text or text in {".", ".."}:
        _fail(path, "deve ser um nome simples sem separadores de caminho")
    return text


def _apply_adls_environment(root: Mapping[str, Any]) -> None:
    adls = root.get("adls")
    if not isinstance(adls, dict):
        return
    mappings = {
        "BANKING_GENERATOR_ADLS_ENABLED": "enabled",
        "BANKING_GENERATOR_ADLS_ACCOUNT_URL": "account_url",
        "BANKING_GENERATOR_ADLS_FILE_SYSTEM": "file_system",
        "BANKING_GENERATOR_ADLS_BASE_DIRECTORY": "base_directory",
        "BANKING_GENERATOR_ADLS_OVERWRITE": "overwrite",
        "BANKING_GENERATOR_ADLS_MAX_CONCURRENCY": "max_concurrency",
    }
    for variable, field in mappings.items():
        if variable in os.environ:
            value = os.environ[variable]
            if field in {"enabled", "overwrite"}:
                if value.lower() not in {"true", "false"}:
                    _fail(variable, "deve ser true ou false")
                value = value.lower() == "true"
            elif field == "max_concurrency":
                try:
                    value = int(value)
                except ValueError:
                    _fail(variable, "deve ser inteiro")
            adls[field] = value


def _apply_event_hubs_environment(root: Mapping[str, Any]) -> None:
    event_hubs = root.get("event_hubs")
    if not isinstance(event_hubs, dict):
        return
    mappings = {
        "BANKING_GENERATOR_EVENT_HUBS_ENABLED": "enabled",
        "BANKING_GENERATOR_EVENT_HUBS_FULLY_QUALIFIED_NAMESPACE": (
            "fully_qualified_namespace"
        ),
        "BANKING_GENERATOR_EVENT_HUBS_EVENTHUB_NAME": "eventhub_name",
        "BANKING_GENERATOR_EVENT_HUBS_EVENTS_PER_SECOND": "events_per_second",
        "BANKING_GENERATOR_EVENT_HUBS_MAX_BATCH_SIZE": "max_batch_size",
        "BANKING_GENERATOR_EVENT_HUBS_STARTING_POSITION": "starting_position",
    }
    for variable, field in mappings.items():
        if variable not in os.environ:
            continue
        value = os.environ[variable]
        if field in {"enabled"}:
            if value.lower() not in {"true", "false"}:
                _fail(variable, "deve ser true ou false")
            value = value.lower() == "true"
        elif field in {"events_per_second", "max_batch_size"}:
            try:
                value = int(value)
            except ValueError:
                _fail(variable, "deve ser inteiro")
        event_hubs[field] = value


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
