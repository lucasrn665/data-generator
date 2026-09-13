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
)
from banking_data_generator.version import BATCH_SCHEMA_VERSION, GENERATOR_VERSION

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
    assert manifest["parameters"]["customers"]["count"] == len(customers)
    assert set(manifest["files"]) == {
        "customers.csv",
        "addresses.csv",
        "accounts.csv",
    }
    assert "generated_at" not in manifest
    assert "timestamp" not in manifest
    assert customers[0].customer_id not in raw.decode()
    assert customers[0].synthetic_name not in raw.decode()
    assert customers[0].synthetic_email not in raw.decode()

    expected_counts = {
        "customers.csv": len(customers),
        "addresses.csv": len(addresses),
        "accounts.csv": len(accounts),
    }
    for filename, expected_count in expected_counts.items():
        path = publication.paths.directory / filename
        metadata = manifest["files"][filename]
        assert metadata["record_count"] == expected_count
        assert metadata["size_bytes"] == path.stat().st_size
        assert metadata["sha256"] == sha256(path.read_bytes()).hexdigest()
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
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "valid"
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


def test_rejects_invalid_existing_manifest(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.manifest.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="JSON UTF-8 válido"):
        _publish(publication_data)


def test_rejects_missing_existing_file(publication_data: tuple) -> None:
    publication = _publish(publication_data)
    publication.paths.addresses.unlink()

    with pytest.raises(ManifestValidationError, match="quatro arquivos esperados"):
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
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "valid"
    )
    final.mkdir(parents=True)

    with pytest.raises(ManifestValidationError, match="quatro arquivos esperados"):
        _publish(publication_data)

    assert final.is_dir()
