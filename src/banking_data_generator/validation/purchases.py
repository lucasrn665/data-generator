"""Validação recalculável de compras, recusas, limites e ledger."""

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC
from decimal import Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    CardStatus,
    DeclineReason,
    EntryDirection,
    LedgerEntryType,
    MerchantStatus,
    TransactionStatus,
    TransactionType,
)
from banking_data_generator.domain.models import (
    Account,
    DebitCard,
    LedgerEntry,
    Merchant,
    Transaction,
)


class TransactionValidationError(ValueError):
    """Indica violação no conjunto de tentativas de compra."""


def validate_card_purchases(
    config: BankingDataGeneratorConfig,
    accounts: Sequence[Account],
    cards: Sequence[DebitCard],
    merchants: Sequence[Merchant],
    transactions: Sequence[Transaction],
    purchase_entries: Sequence[LedgerEntry],
) -> None:
    """Recalcule decisões e garanta correspondência exata com os débitos."""
    if len(transactions) != config.transactions.count:
        _fail("quantidade de tentativas divergente da configuração")
    ids = [transaction.transaction_id for transaction in transactions]
    if len(ids) != len(set(ids)) or any(
        not value.startswith("SYN-TXN-") for value in ids
    ):
        _fail("transaction_id deve ser único e sintético")
    if list(transactions) != sorted(
        transactions, key=lambda item: (item.effective_at, item.transaction_id)
    ):
        _fail("ordenação das transações é instável")

    account_by_id = {account.account_id: account for account in accounts}
    card_by_id = {card.card_id: card for card in cards}
    merchant_by_id = {merchant.merchant_id: merchant for merchant in merchants}
    balances = {account.account_id: account.opening_balance for account in accounts}
    daily_spend: Counter[tuple[str, object]] = Counter()
    entry_by_reference = {entry.reference_id: entry for entry in purchase_entries}
    if len(entry_by_reference) != len(purchase_entries):
        _fail("mais de um lançamento referencia a mesma compra")

    for transaction in transactions:
        account = account_by_id.get(transaction.account_id)
        card = card_by_id.get(transaction.card_id)
        merchant = merchant_by_id.get(transaction.merchant_id)
        if account is None or card is None or merchant is None:
            _fail(f"chave estrangeira inválida em '{transaction.transaction_id}'")
        if card.account_id != account.account_id:
            _fail(f"cartão não pertence à conta em '{transaction.transaction_id}'")
        if transaction.transaction_type is not TransactionType.CARD_PURCHASE:
            _fail(f"tipo inválido em '{transaction.transaction_id}'")
        if transaction.currency != account.currency:
            _fail(f"moeda divergente em '{transaction.transaction_id}'")
        if not isinstance(transaction.amount, Decimal) or transaction.amount <= 0:
            _fail(f"valor inválido em '{transaction.transaction_id}'")
        if transaction.amount.as_tuple().exponent != -2:
            _fail(f"valor sem escala 2 em '{transaction.transaction_id}'")
        if (
            not config.transactions.purchase_amount.min
            <= transaction.amount
            <= config.transactions.purchase_amount.max
        ):
            _fail(f"valor fora da configuração em '{transaction.transaction_id}'")
        if any(
            moment.tzinfo is not UTC
            for moment in (
                transaction.effective_at,
                transaction.event_at,
                transaction.ingested_at,
            )
        ):
            _fail(f"timestamp sem UTC em '{transaction.transaction_id}'")
        if (
            not transaction.effective_at
            <= transaction.event_at
            <= transaction.ingested_at
        ):
            _fail(f"ordem temporal inválida em '{transaction.transaction_id}'")
        if transaction.original_transaction_id is not None:
            _fail(f"referência original inesperada em '{transaction.transaction_id}'")
        if (
            not 0
            <= (config.reference_date - transaction.effective_at.date()).days
            < config.transactions.history_days
        ):
            _fail(f"data fora da janela em '{transaction.transaction_id}'")

        key = (card.card_id, transaction.effective_at.date())
        financial_reason = _reason(
            card,
            merchant,
            transaction.amount,
            balances[account.account_id],
            daily_spend[key],
        )
        entry = entry_by_reference.get(transaction.transaction_id)
        if transaction.status is TransactionStatus.APPROVED:
            if transaction.decline_reason is not None or financial_reason is not None:
                _fail(f"aprovação inválida em '{transaction.transaction_id}'")
            if entry is None:
                _fail(f"débito ausente para '{transaction.transaction_id}'")
            _validate_entry(transaction, entry)
            balances[account.account_id] -= transaction.amount
            daily_spend[key] += transaction.amount
        elif transaction.status is TransactionStatus.DECLINED:
            if transaction.decline_reason is None:
                _fail(f"motivo ausente em '{transaction.transaction_id}'")
            if entry is not None:
                _fail(f"recusa gerou lançamento em '{transaction.transaction_id}'")
            if (
                transaction.decline_reason is DeclineReason.SYNTHETIC_RISK_RULE
                and financial_reason is not None
            ) or (
                transaction.decline_reason is not DeclineReason.SYNTHETIC_RISK_RULE
                and transaction.decline_reason is not financial_reason
            ):
                _fail(f"motivo incoerente em '{transaction.transaction_id}'")
        else:
            _fail(f"status inválido em '{transaction.transaction_id}'")
    if set(entry_by_reference) != {
        transaction.transaction_id
        for transaction in transactions
        if transaction.status is TransactionStatus.APPROVED
    }:
        _fail("lançamentos de compra não correspondem às aprovações")


def reconcile_purchase_balances(
    accounts: Sequence[Account],
    transactions: Sequence[Transaction],
    calculated_balances: Mapping[str, Decimal],
) -> None:
    debits: Counter[str] = Counter()
    for transaction in transactions:
        if transaction.status is TransactionStatus.APPROVED:
            debits[transaction.account_id] += transaction.amount
    for account in accounts:
        expected = account.opening_balance - debits[account.account_id]
        if expected < 0 or calculated_balances.get(account.account_id) != expected:
            _fail(f"saldo final não reconciliado na conta '{account.account_id}'")


def _validate_entry(transaction: Transaction, entry: LedgerEntry) -> None:
    if (
        entry.entry_type is not LedgerEntryType.CARD_PURCHASE
        or entry.direction is not EntryDirection.DEBIT
        or entry.account_id != transaction.account_id
        or entry.amount != transaction.amount
        or entry.currency != transaction.currency
        or entry.effective_at != transaction.effective_at
    ):
        _fail(f"débito incoerente para '{transaction.transaction_id}'")


def _reason(
    card: DebitCard,
    merchant: Merchant,
    amount: Decimal,
    balance: Decimal,
    consumed: Decimal,
) -> DeclineReason | None:
    if card.status is CardStatus.BLOCKED:
        return DeclineReason.CARD_BLOCKED
    if merchant.status is MerchantStatus.INACTIVE:
        return DeclineReason.MERCHANT_INACTIVE
    if amount > balance:
        return DeclineReason.INSUFFICIENT_FUNDS
    if consumed + amount > card.daily_purchase_limit:
        return DeclineReason.DAILY_LIMIT_EXCEEDED
    return None


def _fail(message: str) -> None:
    raise TransactionValidationError(f"Transações inválidas: {message}.")
