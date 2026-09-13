"""Validação de transferências internas e conservação monetária."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, timedelta
from decimal import Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    EntryDirection,
    LedgerEntryType,
    TransferDeclineReason,
    TransferStatus,
    TransferType,
)
from banking_data_generator.domain.models import Account, LedgerEntry, Transfer


class TransferValidationError(ValueError):
    """Indica violação de integridade ou conservação de transferências."""


def validate_internal_transfers(
    config: BankingDataGeneratorConfig,
    accounts: Sequence[Account],
    transfers: Sequence[Transfer],
    entries: Sequence[LedgerEntry],
    balances_before: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Valide tentativas, pares contábeis e saldos sequenciais."""
    account_by_id = {item.account_id: item for item in accounts}
    ids = [item.transfer_id for item in transfers]
    if len(ids) != len(set(ids)):
        _fail("transfer_id duplicado")
    entries_by_reference: dict[str, list[LedgerEntry]] = defaultdict(list)
    entry_ids = [entry.entry_id for entry in entries]
    if len(entry_ids) != len(set(entry_ids)):
        _fail("entry_id duplicado")
    for entry in entries:
        entries_by_reference[entry.reference_id].append(entry)
    transfer_ids = set(ids)
    orphan_references = set(entries_by_reference) - transfer_ids
    if orphan_references:
        _fail(f"lançamento órfão para '{min(orphan_references)}'")
    balances = dict(balances_before)
    for transfer in sorted(
        transfers, key=lambda item: (item.effective_at, item.transfer_id)
    ):
        if not transfer.transfer_id.startswith("SYN-TRF-"):
            _fail(f"prefixo inválido em '{transfer.transfer_id}'")
        source = account_by_id.get(transfer.source_account_id)
        destination = account_by_id.get(transfer.destination_account_id)
        if source is None or destination is None:
            _fail(f"conta inexistente em '{transfer.transfer_id}'")
        if source.account_id == destination.account_id:
            _fail(f"origem e destino iguais em '{transfer.transfer_id}'")
        if (
            source.currency != destination.currency
            or transfer.currency != source.currency
            or transfer.currency != config.currency
        ):
            _fail(f"moeda divergente em '{transfer.transfer_id}'")
        if transfer.transfer_type is not TransferType.INTERNAL_TRANSFER:
            _fail(f"tipo inválido em '{transfer.transfer_id}'")
        if (
            not isinstance(transfer.amount, Decimal)
            or transfer.amount <= 0
            or transfer.amount.as_tuple().exponent != -2
        ):
            _fail(f"valor inválido em '{transfer.transfer_id}'")
        for name in ("effective_at", "event_at", "ingested_at"):
            instant = getattr(transfer, name)
            if instant.tzinfo is not UTC:
                _fail(f"{name} deve usar UTC em '{transfer.transfer_id}'")
            if instant.date() > config.reference_date:
                _fail(
                    f"{name} posterior à data de referência em '{transfer.transfer_id}'"
                )
        if not transfer.effective_at <= transfer.event_at <= transfer.ingested_at:
            _fail(f"timestamps incoerentes em '{transfer.transfer_id}'")
        history_start = config.reference_date - timedelta(
            days=config.transfers.history_days - 1
        )
        if transfer.effective_at.date() < history_start:
            _fail(f"timestamp fora da janela em '{transfer.transfer_id}'")
        related = entries_by_reference.get(transfer.transfer_id, [])
        if transfer.status is TransferStatus.DECLINED:
            if transfer.decline_reason not in set(TransferDeclineReason):
                _fail(f"motivo obrigatório em '{transfer.transfer_id}'")
            if related:
                _fail(
                    "transferência recusada possui lançamento em "
                    f"'{transfer.transfer_id}'"
                )
            continue
        if (
            transfer.status is not TransferStatus.COMPLETED
            or transfer.decline_reason is not None
        ):
            _fail(f"status ou motivo incoerente em '{transfer.transfer_id}'")
        if len(related) != 2:
            _fail(
                f"conclusão deve possuir dois lançamentos em '{transfer.transfer_id}'"
            )
        debit = [
            e
            for e in related
            if e.entry_type is LedgerEntryType.INTERNAL_TRANSFER_DEBIT
        ]
        credit = [
            e
            for e in related
            if e.entry_type is LedgerEntryType.INTERNAL_TRANSFER_CREDIT
        ]
        if len(debit) != 1 or len(credit) != 1:
            _fail(f"par contábil inválido em '{transfer.transfer_id}'")
        debit_entry, credit_entry = debit[0], credit[0]
        if (
            debit_entry.direction is not EntryDirection.DEBIT
            or credit_entry.direction is not EntryDirection.CREDIT
            or debit_entry.account_id != source.account_id
            or credit_entry.account_id != destination.account_id
            or debit_entry.amount != transfer.amount
            or credit_entry.amount != transfer.amount
            or debit_entry.currency != transfer.currency
            or credit_entry.currency != transfer.currency
            or debit_entry.effective_at != transfer.effective_at
            or credit_entry.effective_at != transfer.effective_at
        ):
            _fail(f"lançamentos divergentes em '{transfer.transfer_id}'")
        if balances[source.account_id] < transfer.amount:
            _fail(f"saldo intermediário negativo em '{transfer.transfer_id}'")
        balances[source.account_id] -= transfer.amount
        balances[destination.account_id] += transfer.amount
    debit_total = sum(
        (
            e.amount
            for e in entries
            if e.entry_type is LedgerEntryType.INTERNAL_TRANSFER_DEBIT
        ),
        Decimal("0.00"),
    )
    credit_total = sum(
        (
            e.amount
            for e in entries
            if e.entry_type is LedgerEntryType.INTERNAL_TRANSFER_CREDIT
        ),
        Decimal("0.00"),
    )
    if debit_total != credit_total:
        _fail("débitos e créditos de transferência não conservam valor")
    if sum(balances.values(), Decimal("0.00")) != sum(
        balances_before.values(), Decimal("0.00")
    ):
        _fail("saldo agregado foi alterado pelas transferências")
    if any(value < 0 for value in balances.values()):
        _fail("saldo final negativo")
    return balances


def _fail(message: str) -> None:
    raise TransferValidationError(f"Transferências inválidas: {message}.")
