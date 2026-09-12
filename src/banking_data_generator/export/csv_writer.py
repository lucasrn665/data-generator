"""Escrita CSV atômica dos dados batch válidos."""

from collections.abc import Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile

import pyarrow as pa
import pyarrow.csv as pa_csv

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.models import Account, Address, Customer
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

_WRITE_OPTIONS = pa_csv.WriteOptions(include_header=True, delimiter=",")


def write_batch_csv(
    config: BankingDataGeneratorConfig,
    customers: Sequence[Customer],
    addresses: Sequence[Address],
    accounts: Sequence[Account],
    *,
    project_root: Path = PROJECT_ROOT,
) -> BatchCsvPaths:
    """Converta e grave os três arquivos CSV gerenciados pela etapa."""
    tables = (
        customers_to_table(customers),
        addresses_to_table(addresses),
        accounts_to_table(accounts),
    )
    paths = build_batch_csv_paths(config, project_root=project_root)
    paths.directory.mkdir(parents=True, exist_ok=True)

    for table, destination in zip(
        tables,
        (paths.customers, paths.addresses, paths.accounts),
        strict=True,
    ):
        _write_table_atomically(table, destination)

    return paths


def _write_table_atomically(table: pa.Table, destination: Path) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        pa_csv.write_csv(table, str(temporary_path), write_options=_WRITE_OPTIONS)
        temporary_path.replace(destination)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
