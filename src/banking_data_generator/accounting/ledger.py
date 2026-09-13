"""Geração, ordenação e validação do subledger de contas."""

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, time
from decimal import Decimal

from banking_data_generator.accounting.balances import (
    calculate_all_account_balances,
)
from banking_data_generator.accounting.errors import LedgerValidationError
from banking_data_generator.domain.enums import EntryDirection, LedgerEntryType
from banking_data_generator.domain.models import Account, LedgerEntry

_OPENING_REFERENCE_PREFIX = "SYN-REF-OPEN-"


def generate_opening_entries(accounts: Sequence[Account]) -> list[LedgerEntry]:
    """Gere exatamente um crédito de abertura por conta."""
    entries = [
        LedgerEntry(
            entry_id=f"SYN-ENT-{index:012d}",
            account_id=account.account_id,
            entry_type=LedgerEntryType.OPENING_BALANCE,
            direction=EntryDirection.CREDIT,
            amount=account.opening_balance,
            currency=account.currency,
            effective_at=datetime.combine(account.opened_date, time.min, tzinfo=UTC),
            reference_id=f"{_OPENING_REFERENCE_PREFIX}{index:012d}",
            sequence_number=1,
        )
        for index, account in enumerate(
            sorted(accounts, key=lambda account: account.account_id), start=1
        )
    ]
    return sort_ledger_entries(entries)


def sort_ledger_entries(entries: Sequence[LedgerEntry]) -> list[LedgerEntry]:
    """Ordene de forma estável por conta, instante, sequência e ID."""
    return sorted(
        entries,
        key=lambda entry: (
            entry.account_id,
            entry.effective_at,
            entry.sequence_number,
            entry.entry_id,
        ),
    )


def validate_ledger(
    accounts: Sequence[Account],
    entries: Sequence[LedgerEntry],
) -> None:
    """Valide as invariantes estruturais e monetárias do ledger atual."""
    account_by_id = {account.account_id: account for account in accounts}
    entry_ids = [entry.entry_id for entry in entries]
    if len(entry_ids) != len(set(entry_ids)):
        _fail("entry_id duplicado")

    reference_ids = [entry.reference_id for entry in entries]
    if len(reference_ids) != len(set(reference_ids)):
        _fail("reference_id de abertura duplicado")

    expected_order = sort_ledger_entries(entries)
    if list(entries) != expected_order:
        first = next(
            actual.entry_id
            for actual, expected in zip(entries, expected_order, strict=True)
            if actual != expected
        )
        _fail(f"ordenação instável no lançamento '{first}'")

    for entry in entries:
        account = account_by_id.get(entry.account_id)
        if account is None:
            _fail(
                f"lançamento '{entry.entry_id}' referencia conta inexistente "
                f"'{entry.account_id}'"
            )
        if entry.currency != account.currency:
            _fail(f"moeda divergente no lançamento '{entry.entry_id}'")
        if not isinstance(entry.amount, Decimal):
            _fail(f"valor do lançamento '{entry.entry_id}' deve usar Decimal")
        if entry.amount <= 0:
            _fail(f"valor do lançamento '{entry.entry_id}' deve ser positivo")
        if entry.amount.as_tuple().exponent != -2:
            _fail(f"valor do lançamento '{entry.entry_id}' deve ter escala 2")
        if not isinstance(entry.entry_type, LedgerEntryType):
            _fail(f"tipo inválido no lançamento '{entry.entry_id}'")
        if not isinstance(entry.direction, EntryDirection):
            _fail(f"direção inválida no lançamento '{entry.entry_id}'")
        if entry.entry_type is LedgerEntryType.OPENING_BALANCE:
            if entry.direction is not EntryDirection.CREDIT:
                _fail(f"abertura em débito no lançamento '{entry.entry_id}'")
            if not entry.reference_id.startswith(_OPENING_REFERENCE_PREFIX):
                _fail(f"referência de abertura inválida em '{entry.entry_id}'")
        if entry.effective_at.tzinfo is not UTC:
            _fail(f"effective_at deve usar UTC no lançamento '{entry.entry_id}'")
        if (
            isinstance(entry.sequence_number, bool)
            or not isinstance(entry.sequence_number, int)
            or entry.sequence_number < 0
        ):
            _fail(f"sequence_number inválido no lançamento '{entry.entry_id}'")

    opening_counts = Counter(
        entry.account_id
        for entry in entries
        if entry.entry_type is LedgerEntryType.OPENING_BALANCE
    )
    for account in accounts:
        count = opening_counts[account.account_id]
        if count != 1:
            _fail(
                f"conta '{account.account_id}' deve possuir exatamente uma abertura; "
                f"encontradas: {count}"
            )

    balances = calculate_all_account_balances(accounts, entries)
    for account_id, balance in balances.items():
        if balance < 0:
            _fail(f"saldo negativo para a conta '{account_id}': {balance}")


def _fail(message: str) -> None:
    raise LedgerValidationError(f"Ledger inválido: {message}.")
