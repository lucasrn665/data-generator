from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from banking_data_generator.accounting import (
    AccountingError,
    calculate_account_balance,
    calculate_all_account_balances,
    generate_opening_entries,
    reconcile_opening_balances,
    sort_ledger_entries,
    validate_ledger,
)
from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.domain.enums import EntryDirection, LedgerEntryType
from banking_data_generator.domain.schemas import LEDGER_ENTRY_SCHEMA
from banking_data_generator.export import ledger_entries_to_table
from banking_data_generator.generation import generate_accounts, generate_customers

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def ledger_data() -> tuple[BankingDataGeneratorConfig, list, list]:
    config = load_config(DEFAULT_CONFIG)
    config = replace(config, customers=replace(config.customers, count=5))
    customers = generate_customers(config)
    accounts = generate_accounts(customers, config)
    return config, accounts, generate_opening_entries(accounts)


def test_generates_one_deterministic_opening_credit_per_account(
    ledger_data: tuple,
) -> None:
    _, accounts, entries = ledger_data
    second_generation = generate_opening_entries(accounts)

    assert entries == second_generation
    assert len(entries) == len(accounts)
    assert len({entry.entry_id for entry in entries}) == len(entries)
    assert len({entry.reference_id for entry in entries}) == len(entries)
    assert all(entry.entry_id.startswith("SYN-ENT-") for entry in entries)
    assert all(entry.reference_id.startswith("SYN-REF-OPEN-") for entry in entries)
    assert all(entry.entry_type is LedgerEntryType.OPENING_BALANCE for entry in entries)
    assert all(entry.direction is EntryDirection.CREDIT for entry in entries)
    assert all(entry.sequence_number == 1 for entry in entries)

    accounts_by_id = {account.account_id: account for account in accounts}
    for entry in entries:
        account = accounts_by_id[entry.account_id]
        assert entry.amount == account.opening_balance
        assert isinstance(entry.amount, Decimal)
        assert entry.amount > 0
        assert entry.amount.as_tuple().exponent == -2
        assert entry.currency == account.currency
        assert entry.effective_at == datetime.combine(
            account.opened_date,
            datetime.min.time(),
            tzinfo=UTC,
        )
        assert entry.effective_at.tzinfo is UTC


def test_calculates_credit_debit_and_multiple_entries(ledger_data: tuple) -> None:
    _, accounts, entries = ledger_data
    base = entries[0]
    movements = [
        replace(base, entry_id="SYN-ENT-CREDIT-1", amount=Decimal("100.00")),
        replace(
            base,
            entry_id="SYN-ENT-DEBIT-1",
            direction=EntryDirection.DEBIT,
            amount=Decimal("30.00"),
            sequence_number=2,
        ),
        replace(
            base,
            entry_id="SYN-ENT-CREDIT-2",
            amount=Decimal("5.00"),
            sequence_number=3,
        ),
    ]

    assert calculate_account_balance(base.account_id, movements) == Decimal("75.00")
    balances = calculate_all_account_balances([accounts[0]], movements)
    assert balances == {base.account_id: Decimal("75.00")}


def test_sorts_entries_deterministically(ledger_data: tuple) -> None:
    _, _, entries = ledger_data
    reversed_entries = list(reversed(entries))

    assert sort_ledger_entries(reversed_entries) == entries
    with pytest.raises(AccountingError, match="ordenação instável"):
        validate_ledger([], reversed_entries)


def test_rejects_duplicate_entry_and_reference_ids(ledger_data: tuple) -> None:
    _, accounts, entries = ledger_data
    duplicate_entry = replace(entries[1], entry_id=entries[0].entry_id)
    with pytest.raises(AccountingError, match="entry_id duplicado"):
        validate_ledger(accounts, sort_ledger_entries([entries[0], duplicate_entry]))

    duplicate_reference = replace(entries[1], reference_id=entries[0].reference_id)
    with pytest.raises(AccountingError, match="reference_id.*duplicado"):
        validate_ledger(
            accounts,
            sort_ledger_entries([entries[0], duplicate_reference, *entries[2:]]),
        )


def test_rejects_unknown_account_and_divergent_currency(ledger_data: tuple) -> None:
    _, accounts, entries = ledger_data
    unknown = replace(entries[0], account_id="SYN-ACC-MISSING")
    with pytest.raises(AccountingError, match="SYN-ACC-MISSING"):
        validate_ledger(accounts, sort_ledger_entries([unknown, *entries[1:]]))

    wrong_currency = replace(entries[0], currency="USD")
    with pytest.raises(AccountingError, match=entries[0].entry_id):
        validate_ledger(accounts, [wrong_currency, *entries[1:]])


@pytest.mark.parametrize(
    ("amount", "message"),
    [
        (Decimal("0.00"), "positivo"),
        (Decimal("-1.00"), "positivo"),
        (Decimal("1.0"), "escala 2"),
        (1.00, "Decimal"),
    ],
)
def test_rejects_invalid_amount(
    ledger_data: tuple,
    amount: object,
    message: str,
) -> None:
    _, accounts, entries = ledger_data
    invalid = replace(entries[0], amount=amount)

    with pytest.raises(AccountingError, match=message):
        validate_ledger(accounts, [invalid, *entries[1:]])


def test_rejects_opening_debit_invalid_reference_and_timezone(
    ledger_data: tuple,
) -> None:
    _, accounts, entries = ledger_data
    debit = replace(entries[0], direction=EntryDirection.DEBIT)
    with pytest.raises(AccountingError, match="abertura em débito"):
        validate_ledger(accounts, [debit, *entries[1:]])

    invalid_reference = replace(entries[0], reference_id="OPEN-REAL-1")
    with pytest.raises(AccountingError, match="referência de abertura inválida"):
        validate_ledger(accounts, [invalid_reference, *entries[1:]])

    naive_time = replace(
        entries[0], effective_at=entries[0].effective_at.replace(tzinfo=None)
    )
    with pytest.raises(AccountingError, match="deve usar UTC"):
        validate_ledger(accounts, [naive_time, *entries[1:]])


def test_rejects_non_enum_values_and_negative_sequence(ledger_data: tuple) -> None:
    _, accounts, entries = ledger_data
    invalid_type = replace(entries[0], entry_type="opening_balance")
    with pytest.raises(AccountingError, match="tipo inválido"):
        validate_ledger(accounts, [invalid_type, *entries[1:]])

    invalid_direction = replace(entries[0], direction="credit")
    with pytest.raises(AccountingError, match="direção inválida"):
        validate_ledger(accounts, [invalid_direction, *entries[1:]])

    invalid_sequence = replace(entries[0], sequence_number=-1)
    with pytest.raises(AccountingError, match="sequence_number inválido"):
        validate_ledger(accounts, [invalid_sequence, *entries[1:]])


def test_rejects_duplicate_or_missing_opening(ledger_data: tuple) -> None:
    _, accounts, entries = ledger_data
    duplicate = replace(
        entries[0],
        entry_id="SYN-ENT-DUPLICATE",
        reference_id="SYN-REF-OPEN-DUPLICATE",
        sequence_number=2,
    )
    with pytest.raises(AccountingError, match="exatamente uma abertura"):
        validate_ledger(accounts, sort_ledger_entries([*entries, duplicate]))

    with pytest.raises(AccountingError, match=accounts[0].account_id):
        validate_ledger(accounts, entries[1:])


def test_reconciliation_detects_negative_missing_and_divergent_balances(
    ledger_data: tuple,
) -> None:
    _, accounts, entries = ledger_data
    balances = calculate_all_account_balances(accounts, entries)
    reconcile_opening_balances(accounts, balances)

    negative = dict(balances)
    negative[accounts[0].account_id] = Decimal("-0.01")
    with pytest.raises(AccountingError, match="Saldo negativo"):
        reconcile_opening_balances(accounts, negative)

    missing = dict(balances)
    del missing[accounts[0].account_id]
    with pytest.raises(AccountingError, match="Saldo calculado ausente"):
        reconcile_opening_balances(accounts, missing)

    divergent = dict(balances)
    divergent[accounts[0].account_id] += Decimal("0.01")
    with pytest.raises(AccountingError, match="Saldo calculado divergente"):
        reconcile_opening_balances(accounts, divergent)


def test_ledger_entries_are_compatible_with_pyarrow_schema(ledger_data: tuple) -> None:
    _, _, entries = ledger_data

    table = ledger_entries_to_table(entries)

    assert table.schema == LEDGER_ENTRY_SCHEMA
    assert table.num_rows == len(entries)
    assert table.column_names == LEDGER_ENTRY_SCHEMA.names
    assert all(isinstance(value, Decimal) for value in table["amount"].to_pylist())
    assert all(value.tzinfo is not None for value in table["effective_at"].to_pylist())
