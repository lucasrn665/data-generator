"""Envelopes determinísticos para replay de eventos financeiros."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from banking_data_generator.domain.models import Transaction, Transfer
from banking_data_generator.version import EVENT_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_schema_version: str
    event_type: str
    event_at: str
    ingested_at: str
    sequence_number: int
    partition_key: str
    reference_date: str
    seed: int
    scenario: str
    payload: dict[str, object]

    def to_bytes(self) -> bytes:
        """Serialize sem espaços variáveis e com UTF-8."""
        return (
            json.dumps(
                {
                    "event_id": self.event_id,
                    "event_schema_version": self.event_schema_version,
                    "event_type": self.event_type,
                    "event_at": self.event_at,
                    "ingested_at": self.ingested_at,
                    "sequence_number": self.sequence_number,
                    "partition_key": self.partition_key,
                    "reference_date": self.reference_date,
                    "seed": self.seed,
                    "scenario": self.scenario,
                    "payload": self.payload,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )


def build_replay_events(
    transactions: Sequence[Transaction],
    transfers: Sequence[Transfer],
    *,
    reference_date: str,
    seed: int,
    scenario: str,
) -> tuple[EventEnvelope, ...]:
    """Converta eventos financeiros canônicos para envelopes ordenados."""
    events: list[EventEnvelope] = []
    for item in transactions:
        events.append(
            EventEnvelope(
                event_id=item.transaction_id,
                event_schema_version=EVENT_SCHEMA_VERSION,
                event_type=item.transaction_type.value,
                event_at=_timestamp(item.event_at),
                ingested_at=_timestamp(item.ingested_at),
                sequence_number=0,
                partition_key=item.account_id,
                reference_date=reference_date,
                seed=seed,
                scenario=scenario,
                payload={
                    "account_id": item.account_id,
                    "card_id": item.card_id,
                    "merchant_id": item.merchant_id,
                    "status": item.status.value,
                    "amount": _money(item.amount),
                    "currency": item.currency,
                    "decline_reason": item.decline_reason.value
                    if item.decline_reason
                    else None,
                    "original_transaction_id": item.original_transaction_id,
                },
            )
        )
    for item in transfers:
        events.append(
            EventEnvelope(
                event_id=item.transfer_id,
                event_schema_version=EVENT_SCHEMA_VERSION,
                event_type=item.transfer_type.value,
                event_at=_timestamp(item.event_at),
                ingested_at=_timestamp(item.ingested_at),
                sequence_number=0,
                partition_key=item.source_account_id,
                reference_date=reference_date,
                seed=seed,
                scenario=scenario,
                payload={
                    "source_account_id": item.source_account_id,
                    "destination_account_id": item.destination_account_id,
                    "status": item.status.value,
                    "amount": _money(item.amount),
                    "currency": item.currency,
                    "decline_reason": item.decline_reason.value
                    if item.decline_reason
                    else None,
                },
            )
        )
    ordered = sorted(
        events,
        key=lambda event: (
            event.ingested_at,
            event.event_at,
            event.event_type,
            event.event_id,
        ),
    )
    return tuple(
        replace(event, sequence_number=index) for index, event in enumerate(ordered)
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("eventos devem usar timestamps timezone-aware")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _money(value: Decimal) -> str:
    return f"{value:.2f}"
