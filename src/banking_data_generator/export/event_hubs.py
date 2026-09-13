"""Publicação opcional de envelopes no Azure Event Hubs."""

from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Protocol

from banking_data_generator.config import EventHubsConfig
from banking_data_generator.events import EventEnvelope


class EventHubsPublicationError(RuntimeError):
    """Erro esperado durante autenticação, envio ou fechamento."""


@dataclass(frozen=True, slots=True)
class EventHubsPublicationResult:
    state: str
    events_planned: int
    events_sent: int
    batches: int
    duration_seconds: float
    interrupted: bool = False


class EventHubsDestination(Protocol):
    def publish(
        self, events: Sequence[EventEnvelope], config: EventHubsConfig
    ) -> EventHubsPublicationResult: ...


class AzureEventHubsDestination:
    """Destino real usando DefaultAzureCredential e o SDK oficial."""

    def __init__(self, config: EventHubsConfig | None = None) -> None:
        self._config = config

    def publish(
        self,
        events: Sequence[EventEnvelope],
        config: EventHubsConfig | None = None,
    ) -> EventHubsPublicationResult:
        config = config or self._config
        if config is None:
            raise EventHubsPublicationError("configuração do Event Hubs não informada")
        try:
            from azure.eventhub import EventData, EventHubProducerClient
            from azure.identity import DefaultAzureCredential
        except ImportError as error:
            raise EventHubsPublicationError(
                "dependências Azure para Event Hubs não estão instaladas"
            ) from error
        start = monotonic()
        producer = None
        sent = batches = 0
        interrupted = False
        try:
            producer = EventHubProducerClient(
                fully_qualified_namespace=config.fully_qualified_namespace,
                eventhub_name=config.eventhub_name,
                credential=DefaultAzureCredential(),
            )
            batch = None
            batch_key = None
            batch_count = 0
            for event in events:
                if config.events_per_second:
                    sleep(1 / config.events_per_second)
                if (
                    batch is None
                    or batch_key != event.partition_key
                    or batch_count >= config.max_batch_size
                ):
                    if batch is not None:
                        producer.send_batch(batch)
                        sent += batch_count
                        batches += 1
                    batch = producer.create_batch(partition_key=event.partition_key)
                    batch_key = event.partition_key
                    batch_count = 0
                if not _try_add(batch, EventData(event.to_bytes())):
                    if batch_count == 0:
                        raise EventHubsPublicationError(
                            "um evento excede o limite do lote"
                        )
                    producer.send_batch(batch)
                    sent += batch_count
                    batches += 1
                    batch = producer.create_batch(partition_key=event.partition_key)
                    batch_count = 0
                    if not _try_add(batch, EventData(event.to_bytes())):
                        raise EventHubsPublicationError(
                            "um evento excede o limite do lote"
                        )
                batch_count += 1
            if batch is not None and batch_count:
                producer.send_batch(batch)
                sent += batch_count
                batches += 1
        except KeyboardInterrupt:
            interrupted = True
        except Exception as error:
            if isinstance(error, EventHubsPublicationError):
                raise
            raise EventHubsPublicationError(
                f"falha ao publicar no Event Hubs: {error}"
            ) from error
        finally:
            if producer is not None:
                try:
                    producer.close()
                except Exception as error:
                    if not interrupted:
                        raise EventHubsPublicationError(
                            "falha ao fechar cliente Event Hubs"
                        ) from error
        return EventHubsPublicationResult(
            state="interrupted" if interrupted else "created",
            events_planned=len(events),
            events_sent=sent,
            batches=batches,
            duration_seconds=monotonic() - start,
            interrupted=interrupted,
        )


def _try_add(batch: object, event_data: object) -> bool:
    """Adapte `EventDataBatch.add`, que pode retornar None ou lançar ValueError."""
    try:
        result = batch.add(event_data)  # type: ignore[attr-defined]
    except ValueError:
        return False
    return result is not False
