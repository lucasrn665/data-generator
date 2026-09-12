from collections import Counter
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest

from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.domain.enums import AccountType
from banking_data_generator.domain.models import Account, Address, Customer
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CUSTOMER_SCHEMA,
)
from banking_data_generator.generation import (
    generate_accounts,
    generate_addresses,
    generate_customers,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def small_config() -> BankingDataGeneratorConfig:
    config = load_config(DEFAULT_CONFIG)
    return replace(config, customers=replace(config.customers, count=30))


def generate_initial_domain(
    config: BankingDataGeneratorConfig,
) -> tuple[list[Customer], list[Address], list[Account]]:
    customers = generate_customers(config)
    addresses = generate_addresses(customers, config)
    accounts = generate_accounts(customers, config)
    return customers, addresses, accounts


def test_same_seed_and_config_produce_identical_results(
    small_config: BankingDataGeneratorConfig,
) -> None:
    assert generate_initial_domain(small_config) == generate_initial_domain(
        small_config
    )


def test_different_seeds_change_results_without_breaking_relationships(
    small_config: BankingDataGeneratorConfig,
) -> None:
    other_config = replace(small_config, seed=small_config.seed + 1)
    first = generate_initial_domain(small_config)
    second = generate_initial_domain(other_config)

    assert first != second
    for config, (customers, addresses, accounts) in (
        (small_config, first),
        (other_config, second),
    ):
        customer_ids = {customer.customer_id for customer in customers}
        assert {address.customer_id for address in addresses} <= customer_ids
        assert {account.customer_id for account in accounts} <= customer_ids
        assert all(
            config.accounts.initial_balance.min
            <= account.opening_balance
            <= config.accounts.initial_balance.max
            for account in accounts
        )


def test_ids_are_unique_and_explicitly_synthetic(
    small_config: BankingDataGeneratorConfig,
) -> None:
    customers, addresses, accounts = generate_initial_domain(small_config)

    for records, attribute, prefix in (
        (customers, "customer_id", "SYN-CUS-"),
        (addresses, "address_id", "SYN-ADR-"),
        (accounts, "account_id", "SYN-ACC-"),
    ):
        identifiers = [getattr(record, attribute) for record in records]
        assert len(identifiers) == len(set(identifiers))
        assert all(identifier.startswith(prefix) for identifier in identifiers)


def test_each_customer_has_exactly_one_primary_address(
    small_config: BankingDataGeneratorConfig,
) -> None:
    customers = generate_customers(small_config)
    addresses = generate_addresses(customers, small_config)
    customer_ids = {customer.customer_id for customer in customers}
    primary_counts = Counter(
        address.customer_id for address in addresses if address.is_primary
    )

    assert len(addresses) == len(customers)
    assert {address.customer_id for address in addresses} <= customer_ids
    assert primary_counts == Counter({customer_id: 1 for customer_id in customer_ids})


def test_account_cardinality_and_foreign_keys(
    small_config: BankingDataGeneratorConfig,
) -> None:
    customers = generate_customers(small_config)
    accounts = generate_accounts(customers, small_config)
    customer_ids = {customer.customer_id for customer in customers}
    account_counts = Counter(account.customer_id for account in accounts)

    assert {account.customer_id for account in accounts} <= customer_ids
    for customer_id in customer_ids:
        assert (
            small_config.accounts.min_per_customer
            <= account_counts[customer_id]
            <= small_config.accounts.max_per_customer
        )
        assert account_counts[customer_id] >= 1


def test_account_types_currency_and_opening_balances(
    small_config: BankingDataGeneratorConfig,
) -> None:
    accounts = generate_accounts(generate_customers(small_config), small_config)

    assert all(account.account_type in set(AccountType) for account in accounts)
    assert all(account.currency == small_config.currency for account in accounts)
    assert all(isinstance(account.opening_balance, Decimal) for account in accounts)
    assert all(
        small_config.accounts.initial_balance.min
        <= account.opening_balance
        <= small_config.accounts.initial_balance.max
        for account in accounts
    )
    assert all(
        account.opening_balance.as_tuple().exponent == -2 for account in accounts
    )


def test_dates_are_bounded_by_reference_date(
    small_config: BankingDataGeneratorConfig,
) -> None:
    customers, _, accounts = generate_initial_domain(small_config)

    assert all(
        customer.birth_date <= small_config.reference_date for customer in customers
    )
    assert all(
        customer.created_date <= small_config.reference_date for customer in customers
    )
    assert all(
        account.opened_date <= small_config.reference_date for account in accounts
    )

    future_config = replace(small_config, reference_date=date(2040, 6, 15))
    future_customers, _, future_accounts = generate_initial_domain(future_config)
    reference_delta = future_config.reference_date - small_config.reference_date
    assert all(
        customer.created_date <= future_config.reference_date
        for customer in future_customers
    )
    assert all(
        account.opened_date <= future_config.reference_date
        for account in future_accounts
    )
    assert all(
        future.birth_date - current.birth_date == reference_delta
        and future.created_date - current.created_date == reference_delta
        for current, future in zip(customers, future_customers, strict=True)
    )
    assert all(
        future.opened_date - current.opened_date == reference_delta
        for current, future in zip(accounts, future_accounts, strict=True)
    )


def test_generated_objects_are_compatible_with_pyarrow_schemas(
    small_config: BankingDataGeneratorConfig,
) -> None:
    customers, addresses, accounts = generate_initial_domain(small_config)

    for records, schema in (
        (customers, CUSTOMER_SCHEMA),
        (addresses, ADDRESS_SCHEMA),
        (accounts, ACCOUNT_SCHEMA),
    ):
        table = pa.Table.from_pylist(
            [asdict(record) for record in records], schema=schema
        )
        assert table.schema == schema
        assert table.num_rows == len(records)


def test_components_have_isolated_deterministic_streams(
    small_config: BankingDataGeneratorConfig,
) -> None:
    customers = generate_customers(small_config)
    expected_accounts = generate_accounts(customers, small_config)
    expected_addresses = generate_addresses(customers, small_config)

    generate_customers(small_config)
    generate_addresses(customers, small_config)
    generate_customers(
        replace(
            small_config,
            customers=replace(small_config.customers, count=5),
        )
    )

    assert generate_accounts(customers, small_config) == expected_accounts
    assert generate_addresses(customers, small_config) == expected_addresses
