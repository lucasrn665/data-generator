"""Cálculo puro e reconciliação de saldos derivados do ledger."""

from collections.abc import Mapping, Sequence
from decimal import Decimal

from banking_data_generator.accounting.errors import BalanceReconciliationError
from banking_data_generator.domain.enums import EntryDirection
from banking_data_generator.domain.models import Account, LedgerEntry

_ZERO = Decimal("0.00")


def calculate_account_balance(
    account_id: str,
    entries: Sequence[LedgerEntry],
) -> Decimal:
    """Calcule créditos menos débitos de uma conta, sem alterar estado."""
    balance = _ZERO
    for entry in entries:
        if entry.account_id != account_id:
            continue
        balance += _signed_amount(entry)
    return balance


def calculate_all_account_balances(
    accounts: Sequence[Account],
    entries: Sequence[LedgerEntry],
) -> dict[str, Decimal]:
    """Calcule os saldos de todas as contas em uma única passagem."""
    balances = {account.account_id: _ZERO for account in accounts}
    for entry in entries:
        if entry.account_id not in balances:
            raise BalanceReconciliationError(
                f"Conta inexistente '{entry.account_id}' no cálculo de saldos."
            )
        balances[entry.account_id] += _signed_amount(entry)
    return balances


def reconcile_opening_balances(
    accounts: Sequence[Account],
    balances: Mapping[str, Decimal],
) -> None:
    """Garanta igualdade entre saldo derivado e saldo de abertura."""
    account_ids = {account.account_id for account in accounts}
    unexpected = set(balances) - account_ids
    if unexpected:
        account_id = min(unexpected)
        raise BalanceReconciliationError(
            f"Saldo calculado referencia conta inexistente '{account_id}'."
        )
    for account in accounts:
        if account.account_id not in balances:
            raise BalanceReconciliationError(
                f"Saldo calculado ausente para a conta '{account.account_id}'."
            )
        balance = balances[account.account_id]
        if balance < _ZERO:
            raise BalanceReconciliationError(
                f"Saldo negativo para a conta '{account.account_id}': {balance}."
            )
        if balance != account.opening_balance:
            raise BalanceReconciliationError(
                "Saldo calculado divergente para a conta "
                f"'{account.account_id}': {balance} != {account.opening_balance}."
            )


def _signed_amount(entry: LedgerEntry) -> Decimal:
    if entry.direction is EntryDirection.CREDIT:
        return entry.amount
    if entry.direction is EntryDirection.DEBIT:
        return -entry.amount
    raise BalanceReconciliationError(
        f"Direção inválida no lançamento '{entry.entry_id}'."
    )
