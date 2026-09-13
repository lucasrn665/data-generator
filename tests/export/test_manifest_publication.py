import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

import banking_data_generator.export.csv_writer as writer_module
from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.export import ManifestValidationError, write_batch_csv
from banking_data_generator.export.manifest import serialize_manifest
from banking_data_generator.generation import (
    generate_accounts,
    generate_addresses,
    generate_customers,
    generate_merchants,
)
from banking_data_generator.version import (
    BATCH_SCHEMA_VERSION,
    GENERATOR_VERSION,
    QUALITY_SCENARIO_VERSION,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def publication_data(
    tmp_path: Path,
) -> tuple[BankingDataGeneratorConfig, list, list, list, Path]:
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        output=replace(config.output, directory=Path("exports")),
        customers=replace(config.customers, count=6),
        transactions=replace(config.transactions, count=0),
    )
    customers = generate_customers(config)
    addresses = generate_addresses(customers, config)
    accounts = generate_accounts(customers, config)
    return config, customers, addresses, accounts, tmp_path


def _publish(data: tuple):
    config, customers, addresses, accounts, root = data
    return write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        project_root=root,
    )


def test_manifest_is_deterministic_complete_and_contains_no_records(
    publication_data: tuple,
) -> None:
    config, customers, addresses, accounts, _ = publication_data
    publication = _publish(publication_data)
    raw = publication.paths.manifest.read_bytes()
    manifest = json.loads(raw)

    assert raw.endswith(b"\n")
    assert raw == serialize_manifest(manifest)
    assert manifest["generator_version"] == GENERATOR_VERSION
    assert manifest["schema_version"] == BATCH_SCHEMA_VERSION
    assert manifest["seed"] == config.seed
    assert manifest["reference_date"] == config.reference_date.isoformat()
    assert manifest["currency"] == config.currency
    assert manifest["scenario"] == "valid"
    assert manifest["quality_scenarios"] == []
    assert manifest["expected_violation_count"] == 0
    quality = manifest["quality_summary"]
    assert quality["quality_scenario_version"] == QUALITY_SCENARIO_VERSION
    assert quality["scenario"] == "valid"
    assert quality["affected_count"] == 0
    assert quality["canonical_validation_passed"] is True
    invariants = manifest["accounting_invariants"]
    assert invariants["account_count"] == len(accounts)
    assert invariants["entry_count"] == len(accounts)
    assert invariants["opening_entry_count"] == len(accounts)
    assert invariants["reconciled_account_count"] == len(accounts)
    assert invariants["reconciliation_failure_count"] == 0
    assert invariants["debit_total_brl"] == "0.00"
    assert (
        invariants["opening_credit_total_brl"]
        == f"{sum(account.opening_balance for account in accounts):.2f}"
    )
    assert manifest["parameters"]["customers"]["count"] == len(customers)
    summary = manifest["domain_summary"]
    assert summary["merchant_count"] == config.merchants.count
    assert summary["card_count"] == len(accounts) * config.cards.per_account
    assert (
        summary["active_card_count"] + summary["blocked_card_count"]
        == summary["card_count"]
    )
    assert sum(summary["merchant_count_by_category"].values()) == config.merchants.count
    assert manifest["parameters"]["merchants"]["count"] == config.merchants.count
    assert manifest["parameters"]["cards"]["per_account"] == config.cards.per_account
    assert set(manifest["files"]) == {
        "customers.csv",
        "addresses.csv",
        "accounts.csv",
        "cards.csv",
        "merchants.csv",
        "transactions.csv",
        "transaction_labels.csv",
        "transfers.csv",
        "ledger_entries.csv",
    }
    assert "generated_at" not in manifest
    assert "timestamp" not in manifest
    assert customers[0].customer_id not in raw.decode()
    assert customers[0].synthetic_name not in raw.decode()
    assert customers[0].synthetic_email not in raw.decode()
    merchant = generate_merchants(config)[0]
    assert merchant.synthetic_name not in raw.decode()
    assert merchant.merchant_id not in raw.decode()

    expected_counts = {
        "customers.csv": len(customers),
        "addresses.csv": len(addresses),
        "accounts.csv": len(accounts),
        "cards.csv": len(accounts) * config.cards.per_account,
        "merchants.csv": config.merchants.count,
        "transactions.csv": 0,
        "transaction_labels.csv": 0,
        "transfers.csv": 0,
        "ledger_entries.csv": len(accounts),
    }
    for filename, expected_count in expected_counts.items():
        path = publication.paths.directory / filename
        metadata = manifest["files"][filename]
        assert metadata["record_count"] == expected_count
        assert metadata["size_bytes"] == path.stat().st_size
        assert metadata["sha256"] == sha256(path.read_bytes()).hexdigest()
        assert metadata["path"] == filename
        assert Path(filename).name == filename
        assert not Path(filename).is_absolute()


def test_reexecution_is_idempotent_and_keeps_identical_manifest(
    publication_data: tuple,
) -> None:
    first = _publish(publication_data)
    first_bytes = first.paths.manifest.read_bytes()

    second = _publish(publication_data)

    assert first.created is True
    assert second.created is False
    assert second.paths.manifest.read_bytes() == first_bytes
    assert list(second.paths.directory.parent.glob(".valid.tmp-*")) == []


@pytest.mark.parametrize(
    "phase",
    [
        "_write_csv_files",
        "_validate_staged_files",
        "_write_manifest",
        "_publish_directory",
    ],
)
def test_failure_in_each_phase_never_exposes_final_directory(
    publication_data: tuple,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    config, _, _, _, root = publication_data
    final = (
        root
        / "exports"
        / "schema_version=1.7.3"
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "scenario=valid"
    )

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError(f"failure in {phase}")

    monkeypatch.setattr(writer_module, phase, fail)

    with pytest.raises(OSError, match=f"failure in {phase}"):
        _publish(publication_data)

    assert not final.exists()
    assert list(final.parent.glob(".valid.tmp-*")) == []


def test_cleanup_refuses_directory_it_did_not_create(tmp_path: Path) -> None:
    arbitrary = tmp_path / "arbitrary"
    arbitrary.mkdir()
    marker = arbitrary / "preserve.txt"
    marker.write_text("preserve", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Recusa ao limpar"):
        writer_module._cleanup_staging(arbitrary, tmp_path)

    assert marker.read_text(encoding="utf-8") == "preserve"


def test_rejects_divergent_existing_csv(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.accounts.write_bytes(b"divergent")

    with pytest.raises(ManifestValidationError, match="divergente"):
        _publish(publication_data)

    assert publication.paths.accounts.read_bytes() == b"divergent"


def test_rejects_divergent_existing_cards(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.cards.write_bytes(b"divergent")

    with pytest.raises(ManifestValidationError, match="divergente"):
        _publish(publication_data)

    assert publication.paths.cards.read_bytes() == b"divergent"


def test_rejects_divergent_or_missing_ledger(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.ledger_entries.write_bytes(b"divergent")

    with pytest.raises(ManifestValidationError, match="divergente"):
        _publish(publication_data)

    assert publication.paths.ledger_entries.read_bytes() == b"divergent"


def test_rejects_missing_existing_ledger(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.ledger_entries.unlink()

    with pytest.raises(ManifestValidationError, match="dez arquivos esperados"):
        _publish(publication_data)

    assert not publication.paths.ledger_entries.exists()


def test_old_layout_coexists_with_new_publication(publication_data: tuple) -> None:
    config, _, _, _, root = publication_data
    old = (
        root
        / "exports"
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "valid"
    )
    old.mkdir(parents=True)
    marker = old / "manifest.json"
    marker.write_text("old publication", encoding="utf-8")

    publication = _publish(publication_data)

    assert publication.created is True
    assert marker.read_text(encoding="utf-8") == "old publication"
    assert "schema_version=1.7.3" in publication.paths.directory.parts


def test_ledger_write_failure_does_not_publish_final_directory(
    publication_data: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _, _, _, root = publication_data
    original = writer_module.pa_csv.write_csv

    def fail_ledger(table: object, where: str, **kwargs: object) -> None:
        if Path(where).name == "ledger_entries.csv":
            Path(where).write_bytes(b"partial")
            raise OSError("ledger write failed")
        original(table, where, **kwargs)

    monkeypatch.setattr(writer_module.pa_csv, "write_csv", fail_ledger)

    with pytest.raises(OSError, match="ledger write failed"):
        _publish(publication_data)

    final = (
        root
        / "exports"
        / "schema_version=1.7.3"
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "scenario=valid"
    )
    assert not final.exists()
    assert list(final.parent.glob(".valid.tmp-*")) == []


def test_transfer_write_failure_does_not_publish_final_directory(
    publication_data: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _, _, _, root = publication_data
    original = writer_module.pa_csv.write_csv

    def fail_transfers(table: object, where: str, **kwargs: object) -> None:
        if Path(where).name == "transfers.csv":
            Path(where).write_bytes(b"partial")
            raise OSError("transfer write failed")
        original(table, where, **kwargs)

    monkeypatch.setattr(writer_module.pa_csv, "write_csv", fail_transfers)

    with pytest.raises(OSError, match="transfer write failed"):
        _publish(publication_data)

    final = (
        root
        / "exports"
        / "schema_version=1.7.3"
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "scenario=valid"
    )
    assert not final.exists()
    assert list(final.parent.glob(".valid.tmp-*")) == []


def test_label_write_failure_does_not_publish_final_directory(
    publication_data: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _, _, _, root = publication_data
    original = writer_module.pa_csv.write_csv

    def fail_labels(table: object, where: str, **kwargs: object) -> None:
        if Path(where).name == "transaction_labels.csv":
            Path(where).write_bytes(b"partial")
            raise OSError("label write failed")
        original(table, where, **kwargs)

    monkeypatch.setattr(writer_module.pa_csv, "write_csv", fail_labels)

    with pytest.raises(OSError, match="label write failed"):
        _publish(publication_data)

    final = (
        root
        / "exports"
        / "schema_version=1.7.3"
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "scenario=valid"
    )
    assert not final.exists()
    assert list(final.parent.glob(".valid.tmp-*")) == []


def test_rejects_invalid_existing_manifest(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.manifest.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="JSON UTF-8 válido"):
        _publish(publication_data)


def test_rejects_missing_existing_file(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.addresses.unlink()

    with pytest.raises(ManifestValidationError, match="dez arquivos esperados"):
        _publish(publication_data)


def test_rejects_incompatible_parameters(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    config, customers, addresses, accounts, root = publication_data
    incompatible = replace(
        config,
        accounts=replace(config.accounts, max_per_customer=4),
    )

    with pytest.raises(ManifestValidationError, match="incompatível"):
        write_batch_csv(
            incompatible,
            customers,
            addresses,
            accounts,
            project_root=root,
        )

    assert publication.paths.manifest.is_file()


def test_rejects_preexisting_directory_without_manifest(
    publication_data: tuple,
) -> None:
    config, _, _, _, root = publication_data
    final = (
        root
        / "exports"
        / "schema_version=1.7.3"
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "scenario=valid"
    )
    final.mkdir(parents=True)

    with pytest.raises(ManifestValidationError, match="dez arquivos esperados"):
        _publish(publication_data)

    assert final.is_dir()
