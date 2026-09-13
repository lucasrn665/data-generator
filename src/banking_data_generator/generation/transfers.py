"""Geração determinística de transferências internas e seus lançamentos."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    EntryDirection,
    LedgerEntryType,
    TransferDeclineReason,
    TransferStatus,
    TransferType,
)
from banking_data_generator.domain.models import (
    Account,
    LedgerEntry,
    Transaction,
    Transfer,
)
from banking_data_generator.generation.context import GenerationContext

_CENT = Decimal("0.01")
_CENTS = Decimal("100")


class TransferGenerationError(ValueError):
    """Indica que não é possível gerar tentativas estruturalmente válidas."""


@dataclass(frozen=True, slots=True)
class TransferGenerationResult:
    transfers: list[Transfer]
    ledger_entries: list[LedgerEntry]
    target_declines: int
    planned_declines: int
    additional_declines: int


def generate_internal_transfers(
    accounts: Sequence[Account],
    balances: Mapping[str, Decimal],
    transaction_events: Sequence[Transaction],
    config: BankingDataGeneratorConfig,
) -> TransferGenerationResult:
    """Gere tentativas após os eventos de cartão, sem saldo intermediário negativo."""
    if config.transfers.count and len(accounts) < 2:
        raise TransferGenerationError(
            "Transferências exigem pelo menos duas contas internas disponíveis."
        )
    ordered_accounts = sorted(accounts, key=lambda item: item.account_id)
    context = GenerationContext.create(config.seed, "transfers")
    minimum_cents = int(config.transfers.min_amount * _CENTS)
    maximum_cents = int(config.transfers.max_amount * _CENTS)
    history_start = datetime.combine(
        config.reference_date - timedelta(days=config.transfers.history_days - 1),
        time.min,
        tzinfo=UTC,
    )
    end = datetime.combine(config.reference_date, time.max, tzinfo=UTC)
    last_card_event = max(
        (item.effective_at for item in transaction_events), default=history_start
    )
    start = max(history_start, last_card_event + timedelta(microseconds=1))
    if config.transfers.count and start > end:
        raise TransferGenerationError(
            "Não há instante UTC disponível para transferências "
            "após os eventos de cartão."
        )

    candidates: list[tuple[str, Account, Account, Decimal, datetime]] = []
    span_microseconds = max(0, int((end - start).total_seconds() * 1_000_000))
    for index in range(1, config.transfers.count + 1):
        source_index = context.random.randrange(len(ordered_accounts))
        offset = context.random.randrange(1, len(ordered_accounts))
        destination_index = (source_index + offset) % len(ordered_accounts)
        amount = (
            Decimal(context.random.randint(minimum_cents, maximum_cents)) / _CENTS
        ).quantize(_CENT)
        effective_at = start + timedelta(
            microseconds=context.random.randint(0, span_microseconds)
        )
        candidates.append(
            (
                f"SYN-TRF-{index:012d}",
                ordered_accounts[source_index],
                ordered_accounts[destination_index],
                amount,
                effective_at,
            )
        )
    candidates.sort(key=lambda item: (item[4], item[0]))
    target = int(
        (Decimal(len(candidates)) * config.transfers.declined_rate_overall).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    planned_indexes = set(context.random.sample(range(len(candidates)), target))
    current_balances = dict(balances)
    sequences: Counter[str] = Counter()
    transfers: list[Transfer] = []
    entries: list[LedgerEntry] = []
    planned_declines = 0
    additional_declines = 0

    for position, (transfer_id, source, destination, amount, effective_at) in enumerate(
        candidates
    ):
        reason = None
        if amount > current_balances[source.account_id]:
            reason = TransferDeclineReason.INSUFFICIENT_FUNDS
            additional_declines += 1
        elif position in planned_indexes:
            reason = TransferDeclineReason.SYNTHETIC_RISK_RULE
            planned_declines += 1
        status = TransferStatus.DECLINED if reason else TransferStatus.COMPLETED
        transfer = Transfer(
            transfer_id=transfer_id,
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            transfer_type=TransferType.INTERNAL_TRANSFER,
            status=status,
            amount=amount,
            currency=source.currency,
            effective_at=effective_at,
            event_at=effective_at,
            ingested_at=effective_at,
            decline_reason=reason,
        )
        transfers.append(transfer)
        if status is TransferStatus.COMPLETED:
            current_balances[source.account_id] -= amount
            current_balances[destination.account_id] += amount
            sequences[source.account_id] += 1
            sequences[destination.account_id] += 1
            suffix = transfer_id.removeprefix("SYN-TRF-")
            entries.extend(
                [
                    LedgerEntry(
                        entry_id=f"SYN-ENT-TRD-{suffix}",
                        account_id=source.account_id,
                        entry_type=LedgerEntryType.INTERNAL_TRANSFER_DEBIT,
                        direction=EntryDirection.DEBIT,
                        amount=amount,
                        currency=source.currency,
                        effective_at=effective_at,
                        reference_id=transfer_id,
                        sequence_number=1_000_000 + sequences[source.account_id],
                    ),
                    LedgerEntry(
                        entry_id=f"SYN-ENT-TRC-{suffix}",
                        account_id=destination.account_id,
                        entry_type=LedgerEntryType.INTERNAL_TRANSFER_CREDIT,
                        direction=EntryDirection.CREDIT,
                        amount=amount,
                        currency=destination.currency,
                        effective_at=effective_at,
                        reference_id=transfer_id,
                        sequence_number=1_000_000 + sequences[destination.account_id],
                    ),
                ]
            )
    return TransferGenerationResult(
        transfers=transfers,
        ledger_entries=entries,
        target_declines=target,
        planned_declines=planned_declines,
        additional_declines=additional_declines,
    )
