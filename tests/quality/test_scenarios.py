from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from banking_data_generator.accounting import generate_opening_entries
from banking_data_generator.config import load_config
from banking_data_generator.export.tables import (
    accounts_to_table,
    addresses_to_table,
    cards_to_table,
    customers_to_table,
    ledger_entries_to_table,
    merchants_to_table,
    transaction_labels_to_table,
    transactions_to_table,
    transfers_to_table,
)
from banking_data_generator.generation import (
    generate_accounts,
    generate_addresses,
    generate_cards,
    generate_customers,
    generate_merchants,
)
from banking_data_generator.quality import (
    apply_quality_scenario,
    calculate_affected_count,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def canonical_data() -> tuple:
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        customers=replace(config.customers, count=6),
        merchants=replace(config.merchants, count=4),
        transactions=replace(config.transactions, count=0),
        transfers=replace(config.transfers, count=0),
    )
    customers = generate_customers(config)
    addresses = generate_addresses(customers, config)
    accounts = generate_accounts(customers, config)
    cards = generate_cards(accounts, config)
    tables = {
        "customers.csv": customers_to_table(customers),
        "addresses.csv": addresses_to_table(addresses),
        "accounts.csv": accounts_to_table(accounts),
        "cards.csv": cards_to_table(cards),
        "merchants.csv": merchants_to_table(generate_merchants(config)),
        "transactions.csv": transactions_to_table([]),
        "transaction_labels.csv": transaction_labels_to_table([]),
        "transfers.csv": transfers_to_table([]),
        "ledger_entries.csv": ledger_entries_to_table(
            generate_opening_entries(accounts)
        ),
    }
    return config, tables


def _scenario(config, scenario: str, entity: str, field: str | None):
    return replace(
        config,
        quality=replace(
            config.quality,
            scenario=scenario,
            rate=Decimal("0.50"),
            entity=entity,
            field=field,
        ),
    )


def test_affected_count_uses_round_half_up_without_implicit_minimum() -> None:
    assert calculate_affected_count(5, Decimal("0.10")) == 1
    assert calculate_affected_count(2, Decimal("0.10")) == 0
    assert calculate_affected_count(5, Decimal("0.50")) == 3


@pytest.mark.parametrize(
    ("scenario", "entity", "field"),
    [
        ("duplicate_exact", "customers", None),
        ("duplicate_conflicting", "customers", "synthetic_name"),
        ("required_null", "customers", "synthetic_name"),
        ("orphan_foreign_key", "addresses", "customer_id"),
    ],
)
def test_scenarios_are_deterministic_and_do_not_mutate_canonical_tables(
    canonical_data: tuple,
    scenario: str,
    entity: str,
    field: str | None,
) -> None:
    config, tables = canonical_data
    config = _scenario(config, scenario, entity, field)
    snapshots = {name: table.to_pylist() for name, table in tables.items()}

    first = apply_quality_scenario(tables, config)
    second = apply_quality_scenario(tables, config)

    assert all(table.to_pylist() == snapshots[name] for name, table in tables.items())
    assert all(first.tables[name].equals(second.tables[name]) for name in tables)
    target = f"{entity}.csv"
    assert all(
        first.tables[name].equals(table)
        for name, table in tables.items()
        if name != target
    )
    assert first.affected_count == first.calculated_count == 3
    assert first.expected_violation_count == 3
    if scenario.startswith("duplicate"):
        assert first.published_count == first.original_count + 3
        assert first.additional_row_count == first.duplicate_key_count == 3
    else:
        assert first.published_count == first.original_count


def test_exact_and_conflicting_duplicates_have_expected_content(
    canonical_data: tuple,
) -> None:
    config, tables = canonical_data
    exact = apply_quality_scenario(
        tables, _scenario(config, "duplicate_exact", "customers", None)
    )
    conflict = apply_quality_scenario(
        tables,
        _scenario(config, "duplicate_conflicting", "customers", "synthetic_name"),
    )
    original = tables["customers.csv"].to_pylist()
    assert all(row in original for row in exact.tables["customers.csv"].to_pylist()[6:])
    assert all(
        row["synthetic_name"].endswith("[CONFLITO-SINTETICO]")
        for row in conflict.tables["customers.csv"].to_pylist()[6:]
    )


def test_null_and_orphan_are_the_only_cell_changes(canonical_data: tuple) -> None:
    config, tables = canonical_data
    nulls = apply_quality_scenario(
        tables, _scenario(config, "required_null", "customers", "synthetic_name")
    )
    orphans = apply_quality_scenario(
        tables, _scenario(config, "orphan_foreign_key", "addresses", "customer_id")
    )
    assert (
        sum(
            row["synthetic_name"] is None
            for row in nulls.tables["customers.csv"].to_pylist()
        )
        == 3
    )
    assert (
        sum(
            row["customer_id"].startswith("SYN-MISSING-")
            for row in orphans.tables["addresses.csv"].to_pylist()
        )
        == 3
    )
