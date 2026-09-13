"""Geração determinística de tentativas de compra com cartão de débito."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

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
from banking_data_generator.generation.context import GenerationContext

_CENT = Decimal("0.01")
_CENTS = Decimal("100")


@dataclass(frozen=True, slots=True)
class PurchaseGenerationResult:
    transactions: list[Transaction]
    ledger_entries: list[LedgerEntry]
    target_declines: int
    planned_declines: int
    additional_declines: int


def generate_card_purchases(
    accounts: Sequence[Account],
    cards: Sequence[DebitCard],
    merchants: Sequence[Merchant],
    config: BankingDataGeneratorConfig,
) -> PurchaseGenerationResult:
    """Gere tentativas ordenadas e seus débitos aprovados."""
    if config.transactions.count and (not cards or not merchants):
        raise ValueError("Compras exigem cartões e estabelecimentos disponíveis.")
    context = GenerationContext.create(config.seed, "transactions")
    account_by_id = {account.account_id: account for account in accounts}
    minimum_cents = int(config.transactions.purchase_amount.min * _CENTS)
    maximum_cents = int(config.transactions.purchase_amount.max * _CENTS)
    candidates: list[tuple[str, DebitCard, Merchant, Decimal, datetime]] = []
    history_start = config.reference_date - timedelta(
        days=config.transactions.history_days - 1
    )
    for index in range(1, config.transactions.count + 1):
        card = context.random.choice(cards)
        merchant = context.random.choice(merchants)
        earliest = max(history_start, card.issued_date)
        day = earliest + timedelta(
            days=context.random.randint(0, (config.reference_date - earliest).days)
        )
        effective_at = datetime.combine(day, time.min, tzinfo=UTC) + timedelta(
            seconds=context.random.randint(0, 86_399)
        )
        amount = (
            Decimal(context.random.randint(minimum_cents, maximum_cents)) / _CENTS
        ).quantize(_CENT)
        candidates.append(
            (f"SYN-TXN-{index:012d}", card, merchant, amount, effective_at)
        )
    candidates.sort(key=lambda item: (item[4], item[0]))

    target = int(
        (Decimal(len(candidates)) * config.transactions.declined_rate_overall).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    planned_indexes = set(context.random.sample(range(len(candidates)), target))
    balances = {account.account_id: account.opening_balance for account in accounts}
    daily_spend: Counter[tuple[str, object]] = Counter()
    transactions: list[Transaction] = []
    entries: list[LedgerEntry] = []
    sequences: Counter[str] = Counter()
    planned_declines = 0
    additional_declines = 0

    for position, (transaction_id, card, merchant, amount, effective_at) in enumerate(
        candidates
    ):
        account = account_by_id[card.account_id]
        daily_key = (card.card_id, effective_at.date())
        reason = _financial_decline_reason(
            card, merchant, amount, balances[account.account_id], daily_spend[daily_key]
        )
        if reason is None and position in planned_indexes:
            reason = DeclineReason.SYNTHETIC_RISK_RULE
            planned_declines += 1
        elif reason is not None:
            additional_declines += 1
        status = (
            TransactionStatus.DECLINED
            if reason is not None
            else TransactionStatus.APPROVED
        )
        event_at = effective_at + timedelta(seconds=context.random.randint(0, 30))
        ingested_at = event_at + timedelta(seconds=context.random.randint(0, 30))
        transaction = Transaction(
            transaction_id=transaction_id,
            account_id=account.account_id,
            card_id=card.card_id,
            merchant_id=merchant.merchant_id,
            transaction_type=TransactionType.CARD_PURCHASE,
            status=status,
            amount=amount,
            currency=account.currency,
            effective_at=effective_at,
            event_at=event_at,
            ingested_at=ingested_at,
            decline_reason=reason,
            original_transaction_id=None,
        )
        transactions.append(transaction)
        if status is TransactionStatus.APPROVED:
            balances[account.account_id] -= amount
            daily_spend[daily_key] += amount
            sequences[account.account_id] += 1
            entries.append(
                LedgerEntry(
                    entry_id=f"SYN-ENT-PUR-{transaction_id.removeprefix('SYN-TXN-')}",
                    account_id=account.account_id,
                    entry_type=LedgerEntryType.CARD_PURCHASE,
                    direction=EntryDirection.DEBIT,
                    amount=amount,
                    currency=account.currency,
                    effective_at=effective_at,
                    reference_id=transaction_id,
                    sequence_number=sequences[account.account_id] + 1,
                )
            )
    return PurchaseGenerationResult(
        transactions=transactions,
        ledger_entries=entries,
        target_declines=target,
        planned_declines=planned_declines,
        additional_declines=additional_declines,
    )


def _financial_decline_reason(
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
