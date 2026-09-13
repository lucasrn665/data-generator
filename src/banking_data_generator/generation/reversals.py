"""Seleção e geração determinísticas de estornos integrais."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    EntryDirection,
    LedgerEntryType,
    TransactionStatus,
    TransactionType,
)
from banking_data_generator.domain.models import LedgerEntry, Transaction
from banking_data_generator.generation.context import GenerationContext


@dataclass(frozen=True, slots=True)
class ReversalGenerationResult:
    reversals: list[Transaction]
    ledger_entries: list[LedgerEntry]
    target_reversals: int


def calculate_reversal_target(approved_count: int, rate: Decimal) -> int:
    """Calcule a cota inteira com arredondamento ROUND_HALF_UP."""
    return int(
        (Decimal(approved_count) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def generate_purchase_reversals(
    purchases: Sequence[Transaction], config: BankingDataGeneratorConfig
) -> ReversalGenerationResult:
    """Gere no máximo um estorno integral por compra aprovada elegível."""
    end = datetime.combine(config.reference_date, time.max, tzinfo=UTC)
    approved = sorted(
        (
            item
            for item in purchases
            if item.transaction_type is TransactionType.CARD_PURCHASE
            and item.status is TransactionStatus.APPROVED
        ),
        key=lambda item: item.transaction_id,
    )
    target = calculate_reversal_target(
        len(approved), config.transactions.reversal_rate_of_approved
    )
    eligible = [item for item in approved if item.effective_at < end]
    effective_count = min(target, len(eligible))
    context = GenerationContext.create(config.seed, "reversals")
    selected_indexes = sorted(
        context.random.sample(range(len(eligible)), effective_count)
    )
    selected = [eligible[index] for index in selected_indexes]
    reversals: list[Transaction] = []
    entries: list[LedgerEntry] = []
    for index, original in enumerate(selected, start=1):
        remaining = end - original.effective_at
        effective_at = original.effective_at + remaining / 2
        transaction_id = f"SYN-TXN-REV-{index:012d}"
        reversal = Transaction(
            transaction_id=transaction_id,
            account_id=original.account_id,
            card_id=original.card_id,
            merchant_id=original.merchant_id,
            transaction_type=TransactionType.CARD_PURCHASE_REVERSAL,
            status=TransactionStatus.COMPLETED,
            amount=original.amount,
            currency=original.currency,
            effective_at=effective_at,
            event_at=effective_at,
            ingested_at=effective_at,
            decline_reason=None,
            original_transaction_id=original.transaction_id,
        )
        reversals.append(reversal)
        entries.append(
            LedgerEntry(
                entry_id=f"SYN-ENT-REV-{index:012d}",
                account_id=original.account_id,
                entry_type=LedgerEntryType.CARD_PURCHASE_REVERSAL,
                direction=EntryDirection.CREDIT,
                amount=original.amount,
                currency=original.currency,
                effective_at=effective_at,
                reference_id=transaction_id,
                sequence_number=1_000_000 + index,
            )
        )
    reversals.sort(key=lambda item: (item.effective_at, item.transaction_id))
    return ReversalGenerationResult(reversals, entries, target)
