import csv
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from banking_data_generator.config import load_config
from banking_data_generator.pipeline import run_batch_pipeline

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


def _config(scenario: str):
    config = load_config(DEFAULT_CONFIG)
    return replace(
        config,
        output=replace(config.output, directory=Path("output")),
        customers=replace(config.customers, count=4),
        merchants=replace(config.merchants, count=3),
        transactions=replace(config.transactions, count=10),
        transfers=replace(config.transfers, count=2),
        quality=replace(config.quality, scenario=scenario, rate=Decimal("0.50")),
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.mark.parametrize(
    ("scenario", "expected_columns"),
    [
        ("schema_additive_column", "source_channel"),
        ("schema_missing_column", "merchant_id"),
        ("schema_renamed_column", "counterparty_id"),
        ("schema_incompatible_value", "amount"),
        ("schema_unknown_enum", "status"),
    ],
)
def test_schema_scenarios_are_deterministic_and_target_transactions(
    tmp_path: Path, scenario: str, expected_columns: str
) -> None:
    first = run_batch_pipeline(_config(scenario), tmp_path)
    second = run_batch_pipeline(_config(scenario), tmp_path)
    rows = _rows(first.transactions_file)
    header = (
        list(rows[0])
        if rows
        else first.transactions_file.read_text().splitlines()[0].split(",")
    )
    manifest = __import__("json").loads(first.manifest_file.read_text(encoding="utf-8"))

    assert not second.created
    assert first.transactions_file.read_bytes() == second.transactions_file.read_bytes()
    assert manifest["schema_version"] == "1.7.1"
    assert manifest["quality_summary"]["target_entity"] == "transactions"
    if scenario == "schema_additive_column":
        assert header[-1] == expected_columns
        assert {row[expected_columns] for row in rows} <= {"mobile", "web", "branch"}
    elif scenario == "schema_missing_column":
        assert expected_columns not in header
    elif scenario == "schema_renamed_column":
        assert header[header.index(expected_columns)] == expected_columns
        assert "merchant_id" not in header
    elif scenario == "schema_incompatible_value":
        assert any(row[expected_columns].startswith("INVALID_AMOUNT_") for row in rows)
    else:
        assert any(row[expected_columns] == "pending_review" for row in rows)


def test_schema_scenarios_preserve_financial_files(tmp_path: Path) -> None:
    valid = run_batch_pipeline(_config("valid"), tmp_path)
    mutated = run_batch_pipeline(_config("schema_unknown_enum"), tmp_path)
    for name in (
        "customers.csv",
        "addresses.csv",
        "accounts.csv",
        "cards.csv",
        "merchants.csv",
        "ledger_entries.csv",
        "transfers.csv",
        "transaction_labels.csv",
    ):
        assert (mutated.output_directory / name).read_bytes() == (
            valid.output_directory / name
        ).read_bytes()
