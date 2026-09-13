"""Validação de estornos integrais e de seus efeitos derivados."""

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time
from decimal import Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    EntryDirection,
    LedgerEntryType,
    TransactionStatus,
    TransactionType,
)
from banking_data_generator.domain.models import (
    Account,
    DebitCard,
    LedgerEntry,
    Transaction,
)


class ReversalValidationError(ValueError):
    """Indica um estorno ou efeito contábil inválido."""


def validate_purchase_reversals(
    config: BankingDataGeneratorConfig,
    purchases: Sequence[Transaction],
    reversals: Sequence[Transaction],
    reversal_entries: Sequence[LedgerEntry],
) -> None:
    originals = {item.transaction_id: item for item in purchases}
    reversal_ids = [item.transaction_id for item in reversals]
    if len(reversal_ids) != len(set(reversal_ids)):
        _fail("transaction_id de estorno duplicado")
    references = [item.original_transaction_id for item in reversals]
    if len(references) != len(set(references)):
        _fail("uma compra possui mais de um estorno")
    entry_by_reference = {entry.reference_id: entry for entry in reversal_entries}
    if len(entry_by_reference) != len(reversal_entries):
        _fail("mais de um crédito referencia o mesmo estorno")
    end = datetime.combine(config.reference_date, time.max, tzinfo=UTC)

    for reversal in reversals:
        original_id = reversal.original_transaction_id
        original = originals.get(original_id or "")
        if original is None:
            _fail(f"original inexistente no estorno '{reversal.transaction_id}'")
        if original.transaction_type is not TransactionType.CARD_PURCHASE:
            _fail(f"cadeia de estornos em '{reversal.transaction_id}'")
        if original.status is not TransactionStatus.APPROVED:
            _fail(f"original recusado no estorno '{reversal.transaction_id}'")
        if reversal.transaction_type is not TransactionType.CARD_PURCHASE_REVERSAL:
            _fail(f"tipo inválido no estorno '{reversal.transaction_id}'")
        if reversal.status is not TransactionStatus.COMPLETED:
            _fail(f"status inválido no estorno '{reversal.transaction_id}'")
        if reversal.decline_reason is not None:
            _fail(f"motivo de recusa inesperado em '{reversal.transaction_id}'")
        for field in ("account_id", "card_id", "merchant_id", "currency", "amount"):
            if getattr(reversal, field) != getattr(original, field):
                _fail(f"{field} divergente no estorno '{reversal.transaction_id}'")
        if (
            not isinstance(reversal.amount, Decimal)
            or reversal.amount <= 0
            or reversal.amount.as_tuple().exponent != -2
        ):
            _fail(f"valor inválido no estorno '{reversal.transaction_id}'")
        if (
            reversal.effective_at.tzinfo is not UTC
            or not original.effective_at < reversal.effective_at <= end
        ):
            _fail(f"effective_at inválido no estorno '{reversal.transaction_id}'")
        if (
            not reversal.effective_at <= reversal.event_at <= reversal.ingested_at
            or any(
                value.tzinfo is not UTC
                for value in (reversal.event_at, reversal.ingested_at)
            )
        ):
            _fail(f"ordem temporal inválida no estorno '{reversal.transaction_id}'")
        entry = entry_by_reference.get(reversal.transaction_id)
        if entry is None:
            _fail(f"crédito ausente para o estorno '{reversal.transaction_id}'")
        if (
            entry.entry_type is not LedgerEntryType.CARD_PURCHASE_REVERSAL
            or entry.direction is not EntryDirection.CREDIT
            or entry.account_id != reversal.account_id
            or entry.amount != reversal.amount
            or entry.currency != reversal.currency
            or entry.effective_at != reversal.effective_at
        ):
            _fail(f"crédito divergente para o estorno '{reversal.transaction_id}'")
    if set(entry_by_reference) != set(reversal_ids):
        _fail("existe crédito sem estorno válido")


def calculate_net_daily_consumption(
    cards: Sequence[DebitCard],
    purchases: Sequence[Transaction],
    reversals: Sequence[Transaction],
) -> dict[tuple[str, object], Decimal]:
    limits = {card.card_id: card.daily_purchase_limit for card in cards}
    consumption: Counter[tuple[str, object]] = Counter()
    original_by_id = {item.transaction_id: item for item in purchases}
    for purchase in purchases:
        if purchase.status is TransactionStatus.APPROVED:
            consumption[(purchase.card_id, purchase.effective_at.date())] += (
                purchase.amount
            )
    for reversal in reversals:
        original = original_by_id[reversal.original_transaction_id or ""]
        consumption[(original.card_id, original.effective_at.date())] -= reversal.amount
    for key, amount in consumption.items():
        if amount < 0 or amount > limits[key[0]]:
            _fail(f"consumo diário líquido inválido para o cartão '{key[0]}'")
    return dict(consumption)


def reconcile_reversal_balances(
    accounts: Sequence[Account],
    purchases: Sequence[Transaction],
    reversals: Sequence[Transaction],
    balances: Mapping[str, Decimal],
) -> None:
    effects: Counter[str] = Counter()
    for purchase in purchases:
        if purchase.status is TransactionStatus.APPROVED:
            effects[purchase.account_id] -= purchase.amount
    for reversal in reversals:
        effects[reversal.account_id] += reversal.amount
    for account in accounts:
        expected = account.opening_balance + effects[account.account_id]
        if expected < 0 or balances.get(account.account_id) != expected:
            _fail(f"saldo não reconciliado na conta '{account.account_id}'")


def _fail(message: str) -> None:
    raise ReversalValidationError(f"Estornos inválidos: {message}.")
