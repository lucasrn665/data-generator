from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from banking_data_generator.accounting import generate_opening_entries
from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CUSTOMER_SCHEMA,
    LEDGER_ENTRY_SCHEMA,
)
from banking_data_generator.export.tables import (
    accounts_to_table,
    addresses_to_table,
    customers_to_table,
    ledger_entries_to_table,
)
from banking_data_generator.generation import (
    generate_accounts,
    generate_addresses,
    generate_customers,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def generated_domain() -> tuple[BankingDataGeneratorConfig, list, list, list]:
    config = load_config(DEFAULT_CONFIG)
    config = replace(config, customers=replace(config.customers, count=8))
    customers = generate_customers(config)
    addresses = generate_addresses(customers, config)
    accounts = generate_accounts(customers, config)
    return config, customers, addresses, accounts


def test_customers_convert_to_declared_schema(generated_domain: tuple) -> None:
    _, customers, _, _ = generated_domain

    table = customers_to_table(customers)

    assert table.schema == CUSTOMER_SCHEMA
    assert table.num_rows == len(customers)
    assert table.column_names == CUSTOMER_SCHEMA.names
    assert table["activity_profile"][0].as_py() == customers[0].activity_profile.value
    assert table["status"][0].as_py() == customers[0].status.value


def test_addresses_convert_to_declared_schema(generated_domain: tuple) -> None:
    _, _, addresses, _ = generated_domain

    table = addresses_to_table(addresses)

    assert table.schema == ADDRESS_SCHEMA
    assert table.num_rows == len(addresses)
    assert table.column_names == ADDRESS_SCHEMA.names
    assert table["customer_id"][0].as_py() == addresses[0].customer_id


def test_accounts_preserve_decimal_without_float(generated_domain: tuple) -> None:
    _, _, _, accounts = generated_domain

    table = accounts_to_table(accounts)
    balances = table["opening_balance"].to_pylist()

    assert table.schema == ACCOUNT_SCHEMA
    assert table.num_rows == len(accounts)
    assert table.column_names == ACCOUNT_SCHEMA.names
    assert all(isinstance(balance, Decimal) for balance in balances)
    assert balances == [account.opening_balance for account in accounts]


def test_ledger_entries_preserve_schema_decimal_utc_and_order(
    generated_domain: tuple,
) -> None:
    _, _, _, accounts = generated_domain
    entries = generate_opening_entries(accounts)

    table = ledger_entries_to_table(entries)

    assert table.schema == LEDGER_ENTRY_SCHEMA
    assert table.column_names == LEDGER_ENTRY_SCHEMA.names
    assert table.num_rows == len(accounts)
    assert table["entry_id"].to_pylist() == [entry.entry_id for entry in entries]
    assert all(isinstance(value, Decimal) for value in table["amount"].to_pylist())
    assert all(value.tzinfo is not None for value in table["effective_at"].to_pylist())
