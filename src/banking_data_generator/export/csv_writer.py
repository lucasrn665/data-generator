"""Publicação atômica do conjunto batch válido."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import pyarrow as pa
import pyarrow.csv as pa_csv

from banking_data_generator.accounting import (
    calculate_all_account_balances,
    generate_opening_entries,
    reconcile_opening_balances,
    validate_ledger,
)
from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import EntryDirection, LedgerEntryType
from banking_data_generator.domain.models import Account, Address, Customer, LedgerEntry
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
    ledger_entries_to_table,
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
    ledger_entries: Sequence[LedgerEntry] | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
) -> BatchPublicationResult:
    """Publique atomicamente os CSVs e o manifesto como um único diretório."""
    if ledger_entries is None:
        ledger_entries = generate_opening_entries(accounts)
    validate_ledger(accounts, ledger_entries)
    balances = calculate_all_account_balances(accounts, ledger_entries)
    reconcile_opening_balances(accounts, balances)
    opening_entries = [
        entry
        for entry in ledger_entries
        if entry.entry_type is LedgerEntryType.OPENING_BALANCE
    ]
    opening_credit_total = sum(
        (
            entry.amount
            for entry in opening_entries
            if entry.direction is EntryDirection.CREDIT
        ),
        start=Decimal("0.00"),
    )
    debit_total = sum(
        (
            entry.amount
            for entry in ledger_entries
            if entry.direction is EntryDirection.DEBIT
        ),
        start=Decimal("0.00"),
    )
    accounting_invariants: dict[str, int | str] = {
        "account_count": len(accounts),
        "entry_count": len(ledger_entries),
        "opening_entry_count": len(opening_entries),
        "reconciled_account_count": len(balances),
        "reconciliation_failure_count": 0,
        "opening_credit_total_brl": f"{opening_credit_total:.2f}",
        "debit_total_brl": f"{debit_total:.2f}",
    }
    tables = {
        "customers.csv": customers_to_table(customers),
        "addresses.csv": addresses_to_table(addresses),
        "accounts.csv": accounts_to_table(accounts),
        "ledger_entries.csv": ledger_entries_to_table(ledger_entries),
    }
    record_counts = {
        "customers": len(customers),
        "addresses": len(addresses),
        "accounts": len(accounts),
        "ledger_entries": len(ledger_entries),
    }
    final_paths = build_batch_csv_paths(config, project_root=project_root)
    final_paths.directory.parent.mkdir(parents=True, exist_ok=True)
    staging_directory = Path(
        mkdtemp(prefix=_STAGING_PREFIX, dir=final_paths.directory.parent)
    )
    staging_paths = _paths_in_directory(staging_directory)

    try:
        _write_csv_files(tables, staging_paths)
        manifest = build_manifest(
            config, staging_directory, record_counts, accounting_invariants
        )
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
        "ledger_entries.csv": paths.ledger_entries,
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
        ledger_entries=directory / "ledger_entries.csv",
        manifest=directory / "manifest.json",
    )


def _result(paths: BatchCsvPaths, *, created: bool) -> BatchPublicationResult:
    return BatchPublicationResult(
        paths=paths,
        created=created,
        generator_version=GENERATOR_VERSION,
        schema_version=BATCH_SCHEMA_VERSION,
    )
