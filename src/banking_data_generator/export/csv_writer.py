"""Publicação atômica do conjunto batch válido."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
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
from banking_data_generator.domain.enums import (
    EntryDirection,
    LedgerEntryType,
    MerchantCategory,
)
from banking_data_generator.domain.models import (
    Account,
    Address,
    Customer,
    DebitCard,
    LedgerEntry,
    Merchant,
    Transaction,
    TransactionLabel,
    Transfer,
)
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
    cards_to_table,
    customers_to_table,
    ledger_entries_to_table,
    merchants_to_table,
    transaction_labels_to_table,
    transactions_to_table,
    transfers_to_table,
)
from banking_data_generator.generation import generate_cards, generate_merchants
from banking_data_generator.quality import apply_quality_scenario
from banking_data_generator.validation import (
    calculate_net_daily_consumption,
    reconcile_purchase_balances,
    reconcile_reversal_balances,
    validate_card_purchases,
    validate_cards_and_merchants,
    validate_internal_transfers,
    validate_purchase_reversals,
    validate_transaction_labels,
)
from banking_data_generator.validation.transfers import TransferValidationError
from banking_data_generator.version import (
    BATCH_SCHEMA_VERSION,
    GENERATOR_VERSION,
    TRANSACTION_LABEL_VERSION,
)

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
    cards: Sequence[DebitCard] | None = None,
    merchants: Sequence[Merchant] | None = None,
    transactions: Sequence[Transaction] | None = None,
    transaction_labels: Sequence[TransactionLabel] | None = None,
    transfers: Sequence[Transfer] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> BatchPublicationResult:
    """Publique atomicamente os CSVs e o manifesto como um único diretório."""
    if ledger_entries is None:
        ledger_entries = generate_opening_entries(accounts)
    if cards is None:
        cards = generate_cards(accounts, config)
    if merchants is None:
        merchants = generate_merchants(config)
    validate_cards_and_merchants(config, accounts, cards, merchants)
    transactions = [] if transactions is None else transactions
    transaction_labels = [] if transaction_labels is None else transaction_labels
    transfers = [] if transfers is None else transfers
    purchase_entries = [
        entry
        for entry in ledger_entries
        if entry.entry_type is LedgerEntryType.CARD_PURCHASE
    ]
    reversal_entries = [
        entry
        for entry in ledger_entries
        if entry.entry_type is LedgerEntryType.CARD_PURCHASE_REVERSAL
    ]
    purchases = [
        item for item in transactions if item.transaction_type.value == "card_purchase"
    ]
    reversals = [
        item
        for item in transactions
        if item.transaction_type.value == "card_purchase_reversal"
    ]
    validate_transaction_labels(config, accounts, transactions, transaction_labels)
    validate_card_purchases(
        config, accounts, cards, merchants, purchases, purchase_entries
    )
    validate_purchase_reversals(config, purchases, reversals, reversal_entries)
    net_daily_consumption = calculate_net_daily_consumption(cards, purchases, reversals)
    transfer_entries = [
        entry
        for entry in ledger_entries
        if entry.entry_type
        in {
            LedgerEntryType.INTERNAL_TRANSFER_DEBIT,
            LedgerEntryType.INTERNAL_TRANSFER_CREDIT,
        }
    ]
    pre_transfer_entries = [
        entry
        for entry in ledger_entries
        if entry.entry_type
        not in {
            LedgerEntryType.INTERNAL_TRANSFER_DEBIT,
            LedgerEntryType.INTERNAL_TRANSFER_CREDIT,
        }
    ]
    validate_ledger(accounts, pre_transfer_entries)
    balances_before_transfers = calculate_all_account_balances(
        accounts, pre_transfer_entries
    )
    if reversals:
        reconcile_reversal_balances(
            accounts, purchases, reversals, balances_before_transfers
        )
    elif purchase_entries:
        reconcile_purchase_balances(accounts, purchases, balances_before_transfers)
    else:
        reconcile_opening_balances(accounts, balances_before_transfers)
    expected_balances = validate_internal_transfers(
        config, accounts, transfers, transfer_entries, balances_before_transfers
    )
    validate_ledger(accounts, ledger_entries)
    balances = calculate_all_account_balances(accounts, ledger_entries)
    if balances != expected_balances:
        raise TransferValidationError(
            "Transferências inválidas: saldos finais divergentes do ledger."
        )
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
    category_counts = Counter(merchant.category for merchant in merchants)
    domain_summary: dict[str, Any] = {
        "merchant_count": len(merchants),
        "card_count": len(cards),
        "active_card_count": sum(card.status.value == "active" for card in cards),
        "blocked_card_count": sum(card.status.value == "blocked" for card in cards),
        "merchant_count_by_category": dict(
            sorted(
                {
                    category.value: category_counts[category]
                    for category in MerchantCategory
                }.items()
            )
        ),
    }
    approved = [
        transaction
        for transaction in purchases
        if transaction.status.value == "approved"
    ]
    declined = [
        transaction
        for transaction in purchases
        if transaction.status.value == "declined"
    ]
    target_declines = int(
        (Decimal(len(purchases)) * config.transactions.declined_rate_overall).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    reason_counts = Counter(
        transaction.decline_reason.value
        for transaction in declined
        if transaction.decline_reason is not None
    )
    approved_total = sum((item.amount for item in approved), Decimal("0.00"))
    declined_total = sum((item.amount for item in declined), Decimal("0.00"))
    reversed_total = sum((item.amount for item in reversals), Decimal("0.00"))
    reversal_credit_total = sum(
        (item.amount for item in reversal_entries), Decimal("0.00")
    )
    net_daily_total = sum(net_daily_consumption.values(), Decimal("0.00"))
    transaction_summary: dict[str, Any] = {
        "purchase_attempt_count": len(purchases),
        "approved_purchase_count": len(approved),
        "declined_purchase_count": len(declined),
        "target_decline_count": target_declines,
        "planned_decline_count": reason_counts["synthetic_risk_rule"],
        "additional_decline_count": len(declined)
        - reason_counts["synthetic_risk_rule"],
        "decline_count_by_reason": dict(sorted(reason_counts.items())),
        "approved_amount_total": f"{approved_total:.2f}",
        "declined_amount_total": f"{declined_total:.2f}",
        "new_ledger_debit_count": len(purchase_entries),
        "final_balance_total": f"{sum(balances.values(), Decimal('0.00')):.2f}",
        "reconciliation_failure_count": 0,
        "reversal_target_count": int(
            (
                Decimal(len(approved)) * config.transactions.reversal_rate_of_approved
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        ),
        "reversal_count": len(reversals),
        "transaction_event_count": len(transactions),
        "reversed_amount_total": f"{reversed_total:.2f}",
        "reversal_ledger_credit_count": len(reversal_entries),
        "reversal_ledger_credit_total": f"{reversal_credit_total:.2f}",
        "net_daily_consumption_total": f"{net_daily_total:.2f}",
    }
    label_by_id = {item.transaction_id: item for item in transaction_labels}
    fraud_purchases = [
        item
        for item in purchases
        if label_by_id[item.transaction_id].is_synthetic_fraud
    ]
    fraud_pattern_counts = Counter(
        label.risk_pattern.value
        for label in transaction_labels
        if label.risk_pattern is not None
    )
    effective_fraud_rate = (
        Decimal(len(fraud_purchases)) / Decimal(len(purchases))
        if purchases
        else Decimal("0")
    )
    fraud_label_summary: dict[str, Any] = {
        "labeled_purchase_attempt_count": len(transaction_labels),
        "normal_count": len(transaction_labels) - len(fraud_purchases),
        "target_fraud_count": int(
            (Decimal(len(purchases)) * config.transactions.fraud_rate_overall).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        ),
        "synthetic_fraud_count": len(fraud_purchases),
        "fraud_count_by_pattern": dict(sorted(fraud_pattern_counts.items())),
        "approved_fraud_count": sum(
            item.status.value == "approved" for item in fraud_purchases
        ),
        "declined_fraud_count": sum(
            item.status.value == "declined" for item in fraud_purchases
        ),
        "effective_fraud_rate": f"{effective_fraud_rate:.6f}",
        "label_version": TRANSACTION_LABEL_VERSION,
    }
    completed_transfers = [
        item for item in transfers if item.status.value == "completed"
    ]
    declined_transfers = [item for item in transfers if item.status.value == "declined"]
    transfer_reason_counts = Counter(
        item.decline_reason.value
        for item in declined_transfers
        if item.decline_reason is not None
    )
    transfer_debits = [
        item
        for item in transfer_entries
        if item.entry_type is LedgerEntryType.INTERNAL_TRANSFER_DEBIT
    ]
    transfer_credits = [
        item
        for item in transfer_entries
        if item.entry_type is LedgerEntryType.INTERNAL_TRANSFER_CREDIT
    ]
    transfer_debit_total = sum(
        (item.amount for item in transfer_debits), Decimal("0.00")
    )
    transfer_credit_total = sum(
        (item.amount for item in transfer_credits), Decimal("0.00")
    )
    completed_transfer_total = sum(
        (item.amount for item in completed_transfers), Decimal("0.00")
    )
    declined_transfer_total = sum(
        (item.amount for item in declined_transfers), Decimal("0.00")
    )
    balance_before_total = sum(balances_before_transfers.values(), Decimal("0.00"))
    balance_after_total = sum(balances.values(), Decimal("0.00"))
    conservation_difference = transfer_credit_total - transfer_debit_total
    target_transfer_declines = int(
        (Decimal(len(transfers)) * config.transfers.declined_rate_overall).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    transfer_summary: dict[str, Any] = {
        "transfer_attempt_count": len(transfers),
        "completed_transfer_count": len(completed_transfers),
        "declined_transfer_count": len(declined_transfers),
        "target_decline_count": target_transfer_declines,
        "planned_decline_count": transfer_reason_counts["synthetic_risk_rule"],
        "additional_decline_count": transfer_reason_counts["insufficient_funds"],
        "decline_count_by_reason": dict(sorted(transfer_reason_counts.items())),
        "completed_amount_total": f"{completed_transfer_total:.2f}",
        "declined_amount_total": f"{declined_transfer_total:.2f}",
        "transfer_debit_total": f"{transfer_debit_total:.2f}",
        "transfer_credit_total": f"{transfer_credit_total:.2f}",
        "conservation_difference": f"{conservation_difference:.2f}",
        "aggregate_balance_before_transfers": f"{balance_before_total:.2f}",
        "aggregate_balance_after_transfers": f"{balance_after_total:.2f}",
        "reconciliation_failure_count": 0,
    }
    canonical_tables = {
        "customers.csv": customers_to_table(customers),
        "addresses.csv": addresses_to_table(addresses),
        "accounts.csv": accounts_to_table(accounts),
        "cards.csv": cards_to_table(cards),
        "merchants.csv": merchants_to_table(merchants),
        "transactions.csv": transactions_to_table(transactions),
        "transaction_labels.csv": transaction_labels_to_table(transaction_labels),
        "transfers.csv": transfers_to_table(transfers),
        "ledger_entries.csv": ledger_entries_to_table(ledger_entries),
    }
    quality_result = apply_quality_scenario(canonical_tables, config)
    tables = quality_result.tables
    record_counts = {
        entity: tables[filename].num_rows
        for entity, filename in {
            "customers": "customers.csv",
            "addresses": "addresses.csv",
            "accounts": "accounts.csv",
            "cards": "cards.csv",
            "merchants": "merchants.csv",
            "transactions": "transactions.csv",
            "transaction_labels": "transaction_labels.csv",
            "transfers": "transfers.csv",
            "ledger_entries": "ledger_entries.csv",
        }.items()
    }
    quality_summary: dict[str, Any] = {
        "quality_scenario_version": quality_result.version,
        "scenario": quality_result.scenario,
        "target_entity": quality_result.target_entity,
        "target_field": quality_result.target_field,
        "configured_rate": str(quality_result.configured_rate),
        "calculated_count": quality_result.calculated_count,
        "affected_count": quality_result.affected_count,
        "expected_violation_count": quality_result.expected_violation_count,
        "expected_violation_type": quality_result.expected_violation_type,
        "original_record_count": quality_result.original_count,
        "published_record_count": quality_result.published_count,
        "selected_record_count": quality_result.selected_record_count,
        "additional_row_count": quality_result.additional_row_count,
        "duplicate_key_count": quality_result.duplicate_key_count,
        "canonical_validation_passed": quality_result.canonical_validation_passed,
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
            config,
            staging_directory,
            record_counts,
            accounting_invariants,
            domain_summary,
            transaction_summary,
            transfer_summary,
            fraud_label_summary,
            quality_summary,
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
        "cards.csv": paths.cards,
        "merchants.csv": paths.merchants,
        "transactions.csv": paths.transactions,
        "transaction_labels.csv": paths.transaction_labels,
        "transfers.csv": paths.transfers,
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
        cards=directory / "cards.csv",
        merchants=directory / "merchants.csv",
        transactions=directory / "transactions.csv",
        transaction_labels=directory / "transaction_labels.csv",
        transfers=directory / "transfers.csv",
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
