import csv
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pyarrow.csv as pa_csv
import pytest

from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CUSTOMER_SCHEMA,
)
from banking_data_generator.export import UnsafeOutputPath, write_batch_csv
from banking_data_generator.export.paths import build_batch_csv_paths
from banking_data_generator.generation import (
    generate_accounts,
    generate_addresses,
    generate_customers,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def batch_data(
    tmp_path: Path,
) -> tuple[BankingDataGeneratorConfig, list, list, list, Path]:
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        output=replace(config.output, directory=Path("exports")),
        customers=replace(config.customers, count=12),
    )
    customers = generate_customers(config)
    addresses = generate_addresses(customers, config)
    accounts = generate_accounts(customers, config)
    return config, customers, addresses, accounts, tmp_path


def _read_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def test_writes_expected_files_with_headers_and_rows(batch_data: tuple) -> None:
    config, customers, addresses, accounts, root = batch_data

    paths = write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        project_root=root,
    ).paths

    expected_directory = (
        root / "exports" / "reference_date=2026-01-01" / "seed=42" / "valid"
    )
    assert paths.directory == expected_directory
    assert {
        path.name for path in (paths.customers, paths.addresses, paths.accounts)
    } == {
        "customers.csv",
        "addresses.csv",
        "accounts.csv",
    }
    for path, schema, records in (
        (paths.customers, CUSTOMER_SCHEMA, customers),
        (paths.addresses, ADDRESS_SCHEMA, addresses),
        (paths.accounts, ACCOUNT_SCHEMA, accounts),
    ):
        assert b"\r\n" not in path.read_bytes()
        with path.open(encoding="utf-8", newline="") as csv_file:
            rows = list(csv.reader(csv_file))
        assert rows[0] == schema.names
        assert len(rows) - 1 == len(records)


def test_csv_preserves_dates_money_and_escaped_text(batch_data: tuple) -> None:
    config, customers, addresses, accounts, root = batch_data
    customers[0] = replace(customers[0], synthetic_name='Ana, "Árvore"')
    addresses[0] = replace(
        addresses[0],
        street='Rua "São José", lado A',
        complement='Bloco "B", térreo',
    )
    accounts[0] = replace(accounts[0], opening_balance=Decimal("123.40"))

    paths = write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        project_root=root,
    ).paths
    customer_rows = _read_dicts(paths.customers)
    address_rows = _read_dicts(paths.addresses)
    account_rows = _read_dicts(paths.accounts)

    assert customer_rows[0]["synthetic_name"] == 'Ana, "Árvore"'
    assert customer_rows[0]["birth_date"] == customers[0].birth_date.isoformat()
    assert customer_rows[0]["created_date"] == customers[0].created_date.isoformat()
    assert address_rows[0]["street"] == 'Rua "São José", lado A'
    assert address_rows[0]["complement"] == 'Bloco "B", térreo'
    assert account_rows[0]["opening_balance"] == "123.40"
    assert account_rows[0]["opened_date"] == accounts[0].opened_date.isoformat()


def test_repeated_export_produces_identical_bytes(batch_data: tuple) -> None:
    config, customers, addresses, accounts, root = batch_data
    first_paths = write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        project_root=root,
    ).paths
    first_bytes = {
        path.name: path.read_bytes()
        for path in (first_paths.customers, first_paths.addresses, first_paths.accounts)
    }

    second_paths = write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        project_root=root,
    ).paths

    assert first_bytes == {
        path.name: path.read_bytes()
        for path in (
            second_paths.customers,
            second_paths.addresses,
            second_paths.accounts,
        )
    }


def test_csv_files_can_be_read_back_with_valid_foreign_keys(
    batch_data: tuple,
) -> None:
    config, customers, addresses, accounts, root = batch_data
    paths = write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        project_root=root,
    ).paths

    customer_table = pa_csv.read_csv(
        paths.customers,
        convert_options=pa_csv.ConvertOptions(column_types=CUSTOMER_SCHEMA),
    )
    address_table = pa_csv.read_csv(
        paths.addresses,
        convert_options=pa_csv.ConvertOptions(column_types=ADDRESS_SCHEMA),
    )
    account_table = pa_csv.read_csv(
        paths.accounts,
        convert_options=pa_csv.ConvertOptions(column_types=ACCOUNT_SCHEMA),
    )
    customer_ids = set(customer_table["customer_id"].to_pylist())

    assert customer_table.num_rows == len(customers)
    assert address_table.num_rows == len(addresses)
    assert account_table.num_rows == len(accounts)
    assert set(address_table["customer_id"].to_pylist()) <= customer_ids
    assert set(account_table["customer_id"].to_pylist()) <= customer_ids
    assert all(
        isinstance(value, Decimal)
        for value in account_table["opening_balance"].to_pylist()
    )


@pytest.mark.parametrize(
    "configured",
    [
        Path("../outside"),
        Path("src/output"),
        Path(".git/output"),
        Path("."),
    ],
)
def test_rejects_unsafe_relative_output_paths(
    tmp_path: Path,
    configured: Path,
) -> None:
    config = load_config(DEFAULT_CONFIG)
    config = replace(config, output=replace(config.output, directory=configured))

    with pytest.raises(UnsafeOutputPath, match="Diretório de saída rejeitado"):
        build_batch_csv_paths(config, project_root=tmp_path)


def test_rejects_absolute_output_path(tmp_path: Path) -> None:
    config = load_config(DEFAULT_CONFIG)
    absolute = tmp_path / "output"
    config = replace(config, output=replace(config.output, directory=absolute))

    with pytest.raises(UnsafeOutputPath, match="deve ser relativo"):
        build_batch_csv_paths(config, project_root=tmp_path)


def test_rejects_symlink_that_resolves_outside_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path)
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        output=replace(config.output, directory=Path("escape/output")),
    )

    with pytest.raises(UnsafeOutputPath, match="escapa da raiz"):
        build_batch_csv_paths(config, project_root=root)


def test_failed_write_preserves_final_and_removes_own_temporary_file(
    batch_data: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, customers, addresses, accounts, root = batch_data
    paths = build_batch_csv_paths(config, project_root=root)
    paths.directory.mkdir(parents=True)
    paths.customers.write_bytes(b"previous-complete-file")
    unrelated = paths.directory / "keep-me.txt"
    unrelated.write_text("preserve", encoding="utf-8")

    def fail_after_partial_write(table: object, where: str, **kwargs: object) -> None:
        Path(where).write_bytes(b"partial")
        raise OSError("simulated failure")

    monkeypatch.setattr(pa_csv, "write_csv", fail_after_partial_write)

    with pytest.raises(OSError, match="simulated failure"):
        write_batch_csv(
            config,
            customers,
            addresses,
            accounts,
            project_root=root,
        )

    assert paths.customers.read_bytes() == b"previous-complete-file"
    assert unrelated.read_text(encoding="utf-8") == "preserve"
    assert list(paths.directory.glob("*.tmp")) == []
