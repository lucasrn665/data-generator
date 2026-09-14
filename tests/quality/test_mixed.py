import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from banking_data_generator.config import load_config
from banking_data_generator.pipeline import run_batch_pipeline


def test_mixed_combines_line_anomalies_without_quality_columns(tmp_path: Path) -> None:
    config = load_config("configs/default.yaml")
    config = replace(
        config,
        customers=replace(config.customers, count=4),
        merchants=replace(config.merchants, count=4),
        transactions=replace(config.transactions, count=20),
        transfers=replace(config.transfers, count=1),
        quality=replace(config.quality, scenario="mixed", rate=Decimal("0.50")),
    )
    result = run_batch_pipeline(config, tmp_path)
    assert result.output_directory.name == "scenario=mixed"
    assert "is_invalid" not in result.transactions_file.read_text(encoding="utf-8")
    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))
    assert manifest["scenario"] == "mixed"
    assert manifest["quality_summary"]["quality_scenario_version"] == "2.0.0"
    assert len(result.replay_events) >= result.transaction_event_count


def test_mixed_is_deterministic(tmp_path: Path) -> None:
    config = load_config("configs/default.yaml")
    config = replace(
        config,
        customers=replace(config.customers, count=2),
        merchants=replace(config.merchants, count=2),
        transactions=replace(config.transactions, count=8),
        transfers=replace(config.transfers, count=0),
        quality=replace(config.quality, scenario="mixed", rate=Decimal("0.50")),
    )
    first = run_batch_pipeline(config, tmp_path / "first")
    second = run_batch_pipeline(config, tmp_path / "second")
    assert first.customers_file.read_bytes() == second.customers_file.read_bytes()
    assert [event.to_bytes() for event in first.replay_events] == [
        event.to_bytes() for event in second.replay_events
    ]
