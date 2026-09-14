import csv
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from banking_data_generator.config import load_config
from banking_data_generator.pipeline import run_batch_pipeline

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


def _config(tmp_path: Path, scenario: str, *, seed: int = 42):
    config = load_config(DEFAULT_CONFIG)
    return replace(
        config,
        seed=seed,
        output=replace(config.output, directory=Path("output")),
        customers=replace(config.customers, count=8),
        merchants=replace(config.merchants, count=5),
        transactions=replace(
            config.transactions,
            count=20,
            late_event_rate_overall=Decimal("0.25"),
        ),
        transfers=replace(config.transfers, count=5),
        quality=replace(config.quality, scenario=scenario),
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_late_event_changes_only_arrival_and_physical_order(tmp_path: Path) -> None:
    valid = run_batch_pipeline(_config(tmp_path, "valid"), tmp_path)
    late = run_batch_pipeline(_config(tmp_path, "late_event"), tmp_path)
    valid_rows = _rows(valid.transactions_file)
    late_rows = _rows(late.transactions_file)
    valid_by_id = {row["transaction_id"]: row for row in valid_rows}

    assert late.observed_late_event_count == late.target_late_event_count
    assert late.target_late_event_count > 0
    assert late_rows == sorted(
        late_rows, key=lambda row: (row["ingested_at"], row["transaction_id"])
    )
    changed = 0
    for row in late_rows:
        before = valid_by_id[row["transaction_id"]]
        differences = {key for key in row if row[key] != before[key]}
        assert differences in (set(), {"ingested_at"})
        changed += bool(differences)
        assert row["event_at"].endswith("Z")
        assert row["ingested_at"].endswith("Z")
    assert changed == late.target_late_event_count
    assert valid.observed_late_event_count == 0
    assert valid.final_balance_total == late.final_balance_total
    assert (
        valid.ledger_entries_file.read_bytes() == late.ledger_entries_file.read_bytes()
    )
    assert (
        valid.transaction_labels_file.read_bytes()
        == late.transaction_labels_file.read_bytes()
    )


def test_late_event_is_deterministic_and_manifest_is_coherent(tmp_path: Path) -> None:
    first = run_batch_pipeline(_config(tmp_path, "late_event"), tmp_path)
    second = run_batch_pipeline(_config(tmp_path, "late_event"), tmp_path)
    summary = json.loads(first.manifest_file.read_text(encoding="utf-8"))[
        "late_event_summary"
    ]

    assert not second.created
    assert first.transactions_file.read_bytes() == second.transactions_file.read_bytes()
    assert summary["observed_late_event_count"] == summary["target_late_event_count"]
    assert summary["late_threshold_seconds"] == 300
    assert summary["financial_rules_validated_before_scenario"] is True
    assert first.output_directory.parts[-4] == "schema_version=1.8.0"


def test_canonical_timestamps_are_utc_and_operational(tmp_path: Path) -> None:
    result = run_batch_pipeline(_config(tmp_path, "valid"), tmp_path)
    assert result.maximum_observed_delay_seconds <= 30
    assert result.minimum_observed_delay_seconds >= 0
    # A leitura textual garante o contrato CSV UTC inequívoco.
    assert all(
        row["ingested_at"].endswith("Z") for row in _rows(result.transactions_file)
    )
