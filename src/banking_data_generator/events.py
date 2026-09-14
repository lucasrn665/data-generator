"""Envelopes determinísticos para replay de eventos financeiros."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from banking_data_generator.domain.models import Transaction, Transfer
from banking_data_generator.generation.context import GenerationContext
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


def apply_mixed_event_quality(
    events: Sequence[EventEnvelope], seed: int
) -> tuple[EventEnvelope, ...]:
    """Aplique variações de representação somente ao replay misto."""
    if not events:
        return tuple()
    context = GenerationContext.create(seed, "quality_scenario:mixed:events")
    rows = list(events)
    selected = context.random.sample(
        range(len(rows)), min(len(rows), max(1, len(rows) // 20))
    )
    for offset, index in enumerate(selected):
        event = rows[index]
        payload = dict(event.payload)
        mutation = offset % 8
        if mutation == 0:
            rows.append(event)
        elif mutation == 1 and "merchant_id" in payload:
            payload["merchant_id"] = f"SYN-MISSING-{offset:012d}"
            rows[index] = replace(event, payload=payload)
        elif mutation == 2:
            payload.pop("merchant_id", None)
            rows[index] = replace(event, payload=payload)
        elif mutation == 3 and "amount" in payload:
            payload["amount"] = f"INVALID_AMOUNT_{payload['amount']}"
            rows[index] = replace(event, payload=payload)
        elif mutation == 4:
            payload["status"] = "pending_review"
            rows[index] = replace(event, payload=payload)
        elif mutation == 5:
            payload["source_channel"] = ("mobile", "web", "branch")[offset % 3]
            rows[index] = replace(event, payload=payload)
        elif mutation == 6 and "merchant_id" in payload:
            payload["counterparty_id"] = payload.pop("merchant_id")
            rows[index] = replace(event, payload=payload)
        else:
            event_time = datetime.fromisoformat(event.event_at.replace("Z", "+00:00"))
            rows[index] = replace(
                event,
                ingested_at=_timestamp(event_time + timedelta(hours=1)),
            )
    ordered = sorted(
        rows,
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
