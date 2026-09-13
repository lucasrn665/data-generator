from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import banking_data_generator.pipeline as pipeline_module
from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.pipeline import DatasetValidationError, run_batch_pipeline

DEFAULT_CONFIG = Path(__file__).parents[1] / "configs" / "default.yaml"


@pytest.fixture
def pipeline_config() -> BankingDataGeneratorConfig:
    config = load_config(DEFAULT_CONFIG)
    return replace(
        config,
        output=replace(config.output, directory=Path("output")),
        customers=replace(config.customers, count=10),
    )


def test_complete_pipeline_writes_files_and_returns_counts(
    tmp_path: Path,
    pipeline_config: BankingDataGeneratorConfig,
) -> None:
    result = run_batch_pipeline(pipeline_config, tmp_path)

    assert result.seed == pipeline_config.seed
    assert result.reference_date == pipeline_config.reference_date
    assert result.customer_count == 10
    assert result.address_count == 10
    assert 10 <= result.account_count <= 30
    assert result.output_directory == (
        tmp_path / "output" / "reference_date=2026-01-01" / "seed=42" / "valid"
    )
    assert result.customers_file.is_file()
    assert result.addresses_file.is_file()
    assert result.accounts_file.is_file()


def test_repeated_pipeline_produces_identical_files(
    tmp_path: Path,
    pipeline_config: BankingDataGeneratorConfig,
) -> None:
    first = run_batch_pipeline(pipeline_config, tmp_path)
    first_bytes = {
        path.name: path.read_bytes()
        for path in (first.customers_file, first.addresses_file, first.accounts_file)
    }

    second = run_batch_pipeline(pipeline_config, tmp_path)

    assert first_bytes == {
        path.name: path.read_bytes()
        for path in (
            second.customers_file,
            second.addresses_file,
            second.accounts_file,
        )
    }


def test_validation_failure_happens_before_any_write(
    tmp_path: Path,
    pipeline_config: BankingDataGeneratorConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "generate_accounts", lambda *_: [])

    with pytest.raises(DatasetValidationError, match="quantidade de contas"):
        run_batch_pipeline(pipeline_config, tmp_path)

    assert not (tmp_path / "output").exists()


def test_validator_rejects_duplicate_ids_and_broken_relationships(
    pipeline_config: BankingDataGeneratorConfig,
) -> None:
    customers = pipeline_module.generate_customers(pipeline_config)
    addresses = pipeline_module.generate_addresses(customers, pipeline_config)
    accounts = pipeline_module.generate_accounts(customers, pipeline_config)

    duplicate_customers = [
        customers[0],
        replace(customers[1], customer_id=customers[0].customer_id),
    ]
    with pytest.raises(DatasetValidationError, match="IDs de clientes"):
        pipeline_module.validate_dataset(
            pipeline_config, duplicate_customers, addresses, accounts
        )

    duplicate_addresses = [
        addresses[0],
        replace(addresses[1], address_id=addresses[0].address_id),
        *addresses[2:],
    ]
    with pytest.raises(DatasetValidationError, match="IDs de endereços"):
        pipeline_module.validate_dataset(
            pipeline_config, customers, duplicate_addresses, accounts
        )

    duplicate_accounts = [
        accounts[0],
        replace(accounts[1], account_id=accounts[0].account_id),
        *accounts[2:],
    ]
    with pytest.raises(DatasetValidationError, match="IDs de contas"):
        pipeline_module.validate_dataset(
            pipeline_config, customers, addresses, duplicate_accounts
        )

    with pytest.raises(DatasetValidationError, match="clientes inexistentes"):
        pipeline_module.validate_dataset(
            pipeline_config,
            customers,
            [replace(addresses[0], customer_id="SYN-CUS-MISSING"), *addresses[1:]],
            accounts,
        )

    with pytest.raises(DatasetValidationError, match="endereço principal"):
        pipeline_module.validate_dataset(
            pipeline_config,
            customers,
            [replace(addresses[0], is_primary=False), *addresses[1:]],
            accounts,
        )


def test_validator_rejects_invalid_account_properties(
    pipeline_config: BankingDataGeneratorConfig,
) -> None:
    customers = pipeline_module.generate_customers(pipeline_config)
    addresses = pipeline_module.generate_addresses(customers, pipeline_config)
    accounts = pipeline_module.generate_accounts(customers, pipeline_config)

    invalid_accounts = [
        replace(accounts[0], customer_id="SYN-CUS-MISSING"),
        *accounts[1:],
    ]
    with pytest.raises(DatasetValidationError, match="clientes inexistentes"):
        pipeline_module.validate_dataset(
            pipeline_config, customers, addresses, invalid_accounts
        )

    invalid_accounts = [replace(accounts[0], account_type="credit"), *accounts[1:]]
    with pytest.raises(DatasetValidationError, match="tipo não permitido"):
        pipeline_module.validate_dataset(
            pipeline_config, customers, addresses, invalid_accounts
        )

    invalid_accounts = [replace(accounts[0], currency="USD"), *accounts[1:]]
    with pytest.raises(DatasetValidationError, match="moeda"):
        pipeline_module.validate_dataset(
            pipeline_config, customers, addresses, invalid_accounts
        )

    invalid_accounts = [
        replace(accounts[0], opening_balance=Decimal("50000.01")),
        *accounts[1:],
    ]
    with pytest.raises(DatasetValidationError, match="saldo de abertura"):
        pipeline_module.validate_dataset(
            pipeline_config, customers, addresses, invalid_accounts
        )

    invalid_accounts = [replace(accounts[0], opening_balance=100.0), *accounts[1:]]
    with pytest.raises(DatasetValidationError, match="deve usar Decimal"):
        pipeline_module.validate_dataset(
            pipeline_config, customers, addresses, invalid_accounts
        )
