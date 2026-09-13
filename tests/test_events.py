from dataclasses import replace
from pathlib import Path

from banking_data_generator.config import load_config
from banking_data_generator.export.event_hubs import AzureEventHubsDestination
from banking_data_generator.pipeline import run_batch_pipeline


def test_replay_envelopes_are_deterministic_and_ordered(tmp_path: Path) -> None:
    config = load_config("configs/default.yaml")
    config = replace(
        config,
        customers=replace(config.customers, count=2),
        merchants=replace(config.merchants, count=2),
        transactions=replace(config.transactions, count=3),
        transfers=replace(config.transfers, count=1),
    )
    first = run_batch_pipeline(config, tmp_path / "one")
    second = run_batch_pipeline(config, tmp_path / "two")
    assert [event.to_bytes() for event in first.replay_events] == [
        event.to_bytes() for event in second.replay_events
    ]
    assert [event.sequence_number for event in first.replay_events] == list(range(4))
    assert all(event.event_at.endswith("Z") for event in first.replay_events)
    assert all(event.ingested_at.endswith("Z") for event in first.replay_events)
    assert all(event.partition_key for event in first.replay_events)


def test_replay_contains_only_financial_entities(tmp_path: Path) -> None:
    config = load_config("configs/default.yaml")
    config = replace(
        config,
        customers=replace(config.customers, count=1),
        merchants=replace(config.merchants, count=1),
        transactions=replace(config.transactions, count=1),
        transfers=replace(config.transfers, count=0),
    )
    result = run_batch_pipeline(config, tmp_path)
    allowed = {"card_purchase", "card_purchase_reversal"}
    assert {event.event_type for event in result.replay_events} <= allowed


def test_event_hubs_destination_batches_without_network(monkeypatch) -> None:
    class Batch:
        def __init__(self):
            self.items = []

        def add(self, item):
            self.items.append(item)

    class Producer:
        def __init__(self, **kwargs):
            self.sent = []

        def create_batch(self, partition_key=None):
            return Batch()

        def send_batch(self, batch):
            self.sent.append(batch)

        def close(self):
            pass

    class EventData:
        def __init__(self, body):
            self.body = body

    import sys
    import types

    azure = types.ModuleType("azure")
    eventhub = types.ModuleType("azure.eventhub")
    identity = types.ModuleType("azure.identity")
    eventhub.EventData = EventData
    eventhub.EventHubProducerClient = Producer
    identity.DefaultAzureCredential = lambda: object()
    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.eventhub", eventhub)
    monkeypatch.setitem(sys.modules, "azure.identity", identity)
    config = load_config("configs/default.yaml").event_hubs
    result = AzureEventHubsDestination().publish([], config)
    assert result.events_sent == 0
