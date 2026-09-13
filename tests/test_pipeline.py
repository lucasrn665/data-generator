import csv
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import banking_data_generator.pipeline as pipeline_module
from banking_data_generator.accounting import AccountingError
from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.pipeline import DatasetValidationError, run_batch_pipeline
from banking_data_generator.validation import ExtendedDomainValidationError

DEFAULT_CONFIG = Path(__file__).parents[1] / "configs" / "default.yaml"


@pytest.fixture
def pipeline_config() -> BankingDataGeneratorConfig:
    config = load_config(DEFAULT_CONFIG)
    return replace(
        config,
        output=replace(config.output, directory=Path("output")),
        customers=replace(config.customers, count=10),
        transactions=replace(
            config.transactions,
            count=30,
            reversal_rate_of_approved=Decimal("0.50"),
            fraud_rate_overall=Decimal("0.50"),
        ),
        transfers=replace(config.transfers, count=20),
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
        tmp_path
        / "output"
        / "schema_version=1.6.0"
        / "reference_date=2026-01-01"
        / "seed=42"
        / "scenario=valid"
    )
    assert result.customers_file.is_file()
    assert result.addresses_file.is_file()
    assert result.accounts_file.is_file()
    assert result.ledger_entries_file.is_file()
    assert result.cards_file.is_file()
    assert result.merchants_file.is_file()
    assert result.transactions_file.is_file()
    assert result.transaction_labels_file.is_file()
    assert result.transfers_file.is_file()
    assert result.manifest_file.is_file()
    assert result.ledger_entry_count == (
        result.account_count
        + result.approved_transaction_count
        + result.reversal_count
        + 2 * result.completed_transfer_count
    )
    assert result.opening_credit_total > Decimal("0.00")
    assert result.card_count == result.account_count * pipeline_config.cards.per_account
    assert result.merchant_count == pipeline_config.merchants.count
    assert result.purchase_attempt_count == pipeline_config.transactions.count
    assert (
        result.approved_transaction_count + result.declined_transaction_count
        == result.purchase_attempt_count
    )
    assert (
        result.planned_decline_count + result.additional_decline_count
        == result.declined_transaction_count
    )
    assert result.transaction_event_count == (
        result.purchase_attempt_count + result.reversal_count
    )
    assert result.reversal_count == result.reversal_target_count
    assert result.labeled_purchase_count == result.purchase_attempt_count
    assert result.synthetic_fraud_count == result.target_fraud_count == 15
    assert result.approved_fraud_count + result.declined_fraud_count == 15
    assert result.transfer_attempt_count == 20
    assert result.completed_transfer_count + result.declined_transfer_count == 20
    assert result.generator_version == "0.7.0"
    assert result.schema_version == "1.6.0"
    assert result.created is True
    assert {path.name for path in result.output_directory.iterdir()} == {
        "customers.csv",
        "addresses.csv",
        "accounts.csv",
        "cards.csv",
        "merchants.csv",
        "transactions.csv",
        "transaction_labels.csv",
        "transfers.csv",
        "ledger_entries.csv",
        "manifest.json",
    }
    with result.transactions_file.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        transaction_rows = list(reader)
        assert "is_synthetic_fraud" not in (reader.fieldnames or [])
        assert "risk_pattern" not in (reader.fieldnames or [])
    with result.ledger_entries_file.open(encoding="utf-8", newline="") as file:
        ledger_rows = list(csv.DictReader(file))
    with result.transfers_file.open(encoding="utf-8", newline="") as file:
        transfer_rows = list(csv.DictReader(file))
    assert len(transaction_rows) == result.transaction_event_count
    assert {row["account_id"] for row in transaction_rows} <= {
        row["account_id"] for row in ledger_rows
    }
    approved_ids = {
        row["transaction_id"] for row in transaction_rows if row["status"] == "approved"
    }
    assert approved_ids == {
        row["reference_id"]
        for row in ledger_rows
        if row["entry_type"] == "card_purchase"
    }
    purchase_rows = [
        row for row in transaction_rows if row["transaction_type"] == "card_purchase"
    ]
    reversal_rows = [
        row
        for row in transaction_rows
        if row["transaction_type"] == "card_purchase_reversal"
    ]
    assert all(row["original_transaction_id"] == "" for row in purchase_rows)
    assert all(row["original_transaction_id"] in approved_ids for row in reversal_rows)
    account_ids = {row["account_id"] for row in ledger_rows}
    assert {row["source_account_id"] for row in transfer_rows} <= account_ids
    assert {row["destination_account_id"] for row in transfer_rows} <= account_ids
    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))
    summary = manifest["transaction_summary"]
    assert summary["purchase_attempt_count"] == result.purchase_attempt_count
    assert summary["approved_purchase_count"] == result.approved_transaction_count
    assert summary["declined_purchase_count"] == result.declined_transaction_count
    assert summary["new_ledger_debit_count"] == result.approved_transaction_count
    assert summary["reconciliation_failure_count"] == 0
    assert summary["reversal_target_count"] == result.reversal_target_count
    assert summary["reversal_count"] == result.reversal_count
    assert summary["transaction_event_count"] == result.transaction_event_count
    assert summary["reversal_ledger_credit_count"] == result.reversal_count
    assert summary["reversed_amount_total"] == f"{result.reversed_amount_total:.2f}"
    for field in (
        "approved_amount_total",
        "declined_amount_total",
        "final_balance_total",
    ):
        assert isinstance(summary[field], str)
        assert len(summary[field].partition(".")[2]) == 2
    transfer_summary = manifest["transfer_summary"]
    assert transfer_summary["transfer_attempt_count"] == result.transfer_attempt_count
    assert (
        transfer_summary["completed_transfer_count"] == result.completed_transfer_count
    )
    assert transfer_summary["declined_transfer_count"] == result.declined_transfer_count
    assert transfer_summary["conservation_difference"] == "0.00"
    assert (
        transfer_summary["aggregate_balance_before_transfers"]
        == transfer_summary["aggregate_balance_after_transfers"]
    )
    assert manifest["files"]["transfers.csv"]["record_count"] == 20
    fraud_summary = manifest["fraud_label_summary"]
    assert fraud_summary["labeled_purchase_attempt_count"] == 30
    assert fraud_summary["synthetic_fraud_count"] == 15
    assert fraud_summary["target_fraud_count"] == 15
    assert fraud_summary["label_version"] == "1.0.0"
    assert manifest["files"]["transaction_labels.csv"]["record_count"] == 30


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
    assert second.created is False


def test_validation_failure_happens_before_any_write(
    tmp_path: Path,
    pipeline_config: BankingDataGeneratorConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "generate_accounts", lambda *_: [])

    with pytest.raises(DatasetValidationError, match="quantidade de contas"):
        run_batch_pipeline(pipeline_config, tmp_path)

    assert not (tmp_path / "output").exists()


def test_reconciliation_failure_happens_before_publication(
    tmp_path: Path,
    pipeline_config: BankingDataGeneratorConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_reconciliation(*args: object) -> None:
        raise AccountingError("simulated reconciliation failure")

    monkeypatch.setattr(
        pipeline_module,
        "reconcile_reversal_balances",
        fail_reconciliation,
    )

    with pytest.raises(AccountingError, match="simulated reconciliation failure"):
        run_batch_pipeline(pipeline_config, tmp_path)

    assert not (tmp_path / "output").exists()


def test_invalid_card_stops_pipeline_before_publication(
    tmp_path: Path,
    pipeline_config: BankingDataGeneratorConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "generate_cards", lambda *_: [])

    with pytest.raises(ExtendedDomainValidationError, match="quantidade de cartões"):
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
