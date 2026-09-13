from dataclasses import replace
from datetime import UTC
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest

from banking_data_generator.accounting import (
    calculate_all_account_balances,
    generate_opening_entries,
    sort_ledger_entries,
    validate_ledger,
)
from banking_data_generator.config import load_config
from banking_data_generator.domain.enums import (
    EntryDirection,
    LedgerEntryType,
    TransferStatus,
)
from banking_data_generator.domain.schemas import TRANSFER_SCHEMA
from banking_data_generator.export import transfers_to_table
from banking_data_generator.generation import (
    generate_accounts,
    generate_customers,
    generate_internal_transfers,
)
from banking_data_generator.validation import (
    TransferValidationError,
    validate_internal_transfers,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def transfer_data() -> tuple:
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        customers=replace(config.customers, count=5),
        transfers=replace(
            config.transfers,
            count=20,
            min_amount=Decimal("1.00"),
            max_amount=Decimal("25.00"),
            declined_rate_overall=Decimal("0.25"),
        ),
    )
    customers = generate_customers(config)
    accounts = generate_accounts(customers, config)
    opening = generate_opening_entries(accounts)
    balances = calculate_all_account_balances(accounts, opening)
    return config, accounts, opening, balances


def test_generation_is_deterministic_valid_and_conserves_money(
    transfer_data: tuple,
) -> None:
    config, accounts, opening, balances = transfer_data
    first = generate_internal_transfers(accounts, balances, [], config)
    second = generate_internal_transfers(accounts, balances, [], config)

    assert first == second
    assert first.target_declines == 5
    assert first.planned_declines + first.additional_declines == sum(
        item.status is TransferStatus.DECLINED for item in first.transfers
    )
    assert len({item.transfer_id for item in first.transfers}) == len(first.transfers)
    assert all(item.transfer_id.startswith("SYN-TRF-") for item in first.transfers)
    assert all(
        item.source_account_id != item.destination_account_id
        for item in first.transfers
    )
    assert all(item.effective_at.tzinfo is UTC for item in first.transfers)
    assert all(
        item.effective_at.date() <= config.reference_date for item in first.transfers
    )
    completed = [
        item for item in first.transfers if item.status is TransferStatus.COMPLETED
    ]
    declined = [
        item for item in first.transfers if item.status is TransferStatus.DECLINED
    ]
    assert len(first.ledger_entries) == 2 * len(completed)
    assert {item.reference_id for item in first.ledger_entries} == {
        item.transfer_id for item in completed
    }
    assert not (
        {item.transfer_id for item in declined}
        & {item.reference_id for item in first.ledger_entries}
    )
    assert sum(
        item.amount
        for item in first.ledger_entries
        if item.direction is EntryDirection.DEBIT
    ) == sum(
        item.amount
        for item in first.ledger_entries
        if item.direction is EntryDirection.CREDIT
    )
    expected = validate_internal_transfers(
        config, accounts, first.transfers, first.ledger_entries, balances
    )
    ledger = sort_ledger_entries([*opening, *first.ledger_entries])
    validate_ledger(accounts, ledger)
    assert calculate_all_account_balances(accounts, ledger) == expected
    assert min(expected.values()) >= Decimal("0.00")
    assert sum(expected.values()) == sum(balances.values())


def test_seed_is_independent_and_changes_results(transfer_data: tuple) -> None:
    config, accounts, _, balances = transfer_data
    changed = replace(config, seed=config.seed + 1)
    assert generate_internal_transfers(accounts, balances, [], config) != (
        generate_internal_transfers(accounts, balances, [], changed)
    )
    unrelated_change = replace(
        config, transactions=replace(config.transactions, count=999)
    )
    assert generate_internal_transfers(accounts, balances, [], config) == (
        generate_internal_transfers(accounts, balances, [], unrelated_change)
    )


def test_insufficient_funds_declines_without_entries(transfer_data: tuple) -> None:
    config, accounts, _, balances = transfer_data
    too_large = max(balances.values()) + Decimal("1.00")
    config = replace(
        config,
        transfers=replace(
            config.transfers,
            count=4,
            min_amount=too_large,
            max_amount=too_large,
            declined_rate_overall=Decimal("0.00"),
        ),
    )

    result = generate_internal_transfers(accounts, balances, [], config)

    assert result.additional_declines == 4
    assert not result.ledger_entries
    assert all(item.status is TransferStatus.DECLINED for item in result.transfers)


def test_schema_round_trip_preserves_decimal_and_utc(transfer_data: tuple) -> None:
    config, accounts, _, balances = transfer_data
    result = generate_internal_transfers(accounts, balances, [], config)
    table = transfers_to_table(result.transfers)
    assert table.schema == TRANSFER_SCHEMA
    assert table.column("amount").type == pa.decimal128(18, 2)
    assert all(
        isinstance(value, Decimal) for value in table.column("amount").to_pylist()
    )
    assert all(
        value.tzinfo is not None for value in table.column("effective_at").to_pylist()
    )


def test_validator_detects_missing_extra_and_divergent_entries(
    transfer_data: tuple,
) -> None:
    config, accounts, _, balances = transfer_data
    result = generate_internal_transfers(accounts, balances, [], config)
    completed = next(
        item for item in result.transfers if item.status is TransferStatus.COMPLETED
    )
    related = [
        item
        for item in result.ledger_entries
        if item.reference_id == completed.transfer_id
    ]
    with pytest.raises(TransferValidationError, match="dois lançamentos"):
        validate_internal_transfers(
            config,
            accounts,
            result.transfers,
            [item for item in result.ledger_entries if item != related[0]],
            balances,
        )
    duplicate = replace(related[0], entry_id="SYN-ENT-TRD-EXTRA")
    with pytest.raises(TransferValidationError, match="dois lançamentos"):
        validate_internal_transfers(
            config,
            accounts,
            result.transfers,
            [*result.ledger_entries, duplicate],
            balances,
        )
    divergent = replace(related[0], amount=related[0].amount + Decimal("1.00"))
    entries = [
        divergent if item == related[0] else item for item in result.ledger_entries
    ]
    with pytest.raises(TransferValidationError, match="divergentes"):
        validate_internal_transfers(
            config, accounts, result.transfers, entries, balances
        )


def test_completed_entries_have_correct_types_and_unique_ids(
    transfer_data: tuple,
) -> None:
    config, accounts, _, balances = transfer_data
    entries = generate_internal_transfers(accounts, balances, [], config).ledger_entries
    assert len({item.entry_id for item in entries}) == len(entries)
    assert all(item.entry_id.startswith("SYN-ENT-TR") for item in entries)
    assert {item.entry_type for item in entries} <= {
        LedgerEntryType.INTERNAL_TRANSFER_DEBIT,
        LedgerEntryType.INTERNAL_TRANSFER_CREDIT,
    }
