"""Publicação atômica do conjunto batch válido."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import pyarrow as pa
import pyarrow.csv as pa_csv

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.models import Account, Address, Customer
from banking_data_generator.export.manifest import (
    MANAGED_FILENAMES,
    build_manifest,
    serialize_manifest,
    validate_csv_files,
    validate_existing_publication,
)
from banking_data_generator.export.paths import (
    PROJECT_ROOT,
    BatchCsvPaths,
    build_batch_csv_paths,
)
from banking_data_generator.export.tables import (
    accounts_to_table,
    addresses_to_table,
    customers_to_table,
)
from banking_data_generator.version import BATCH_SCHEMA_VERSION, GENERATOR_VERSION

_WRITE_OPTIONS = pa_csv.WriteOptions(include_header=True, delimiter=",")
_STAGING_PREFIX = ".valid.tmp-"


@dataclass(frozen=True, slots=True)
class BatchPublicationResult:
    """Resultado da criação ou validação idempotente de uma publicação."""

    paths: BatchCsvPaths
    created: bool
    generator_version: str
    schema_version: str


def write_batch_csv(
    config: BankingDataGeneratorConfig,
    customers: Sequence[Customer],
    addresses: Sequence[Address],
    accounts: Sequence[Account],
    *,
    project_root: Path = PROJECT_ROOT,
) -> BatchPublicationResult:
    """Publique atomicamente os CSVs e o manifesto como um único diretório."""
    tables = {
        "customers.csv": customers_to_table(customers),
        "addresses.csv": addresses_to_table(addresses),
        "accounts.csv": accounts_to_table(accounts),
    }
    record_counts = {
        "customers": len(customers),
        "addresses": len(addresses),
        "accounts": len(accounts),
    }
    final_paths = build_batch_csv_paths(config, project_root=project_root)
    final_paths.directory.parent.mkdir(parents=True, exist_ok=True)
    staging_directory = Path(
        mkdtemp(prefix=_STAGING_PREFIX, dir=final_paths.directory.parent)
    )
    staging_paths = _paths_in_directory(staging_directory)

    try:
        _write_csv_files(tables, staging_paths)
        manifest = build_manifest(config, staging_directory, record_counts)
        _validate_staged_files(staging_directory, manifest)
        _write_manifest(staging_paths.manifest, manifest)

        if final_paths.directory.exists():
            validate_existing_publication(final_paths.directory, manifest)
            _cleanup_staging(staging_directory, final_paths.directory.parent)
            return _result(final_paths, created=False)

        _publish_directory(staging_directory, final_paths.directory)
        return _result(final_paths, created=True)
    except BaseException:
        if staging_directory.exists():
            _cleanup_staging(staging_directory, final_paths.directory.parent)
        raise


def _write_csv_files(
    tables: Mapping[str, pa.Table],
    paths: BatchCsvPaths,
) -> None:
    destinations = {
        "customers.csv": paths.customers,
        "addresses.csv": paths.addresses,
        "accounts.csv": paths.accounts,
    }
    for filename, table in tables.items():
        pa_csv.write_csv(
            table, str(destinations[filename]), write_options=_WRITE_OPTIONS
        )


def _validate_staged_files(
    directory: Path,
    manifest: Mapping[str, Any],
) -> None:
    validate_csv_files(directory, manifest)


def _write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    path.write_bytes(serialize_manifest(manifest))


def _publish_directory(staging: Path, final: Path) -> None:
    staging.rename(final)


def _cleanup_staging(staging: Path, expected_parent: Path) -> None:
    if (
        staging.parent != expected_parent
        or not staging.name.startswith(_STAGING_PREFIX)
        or staging.is_symlink()
        or not staging.is_dir()
    ):
        raise RuntimeError(
            f"Recusa ao limpar diretório temporário inesperado: '{staging}'."
        )
    for filename in MANAGED_FILENAMES:
        path = staging / filename
        if path.is_dir():
            raise RuntimeError(
                f"Recusa ao limpar entrada temporária inesperada: '{path}'."
            )
        path.unlink(missing_ok=True)
    staging.rmdir()


def _paths_in_directory(directory: Path) -> BatchCsvPaths:
    return BatchCsvPaths(
        directory=directory,
        customers=directory / "customers.csv",
        addresses=directory / "addresses.csv",
        accounts=directory / "accounts.csv",
        manifest=directory / "manifest.json",
    )


def _result(paths: BatchCsvPaths, *, created: bool) -> BatchPublicationResult:
    return BatchPublicationResult(
        paths=paths,
        created=created,
        generator_version=GENERATOR_VERSION,
        schema_version=BATCH_SCHEMA_VERSION,
    )
