"""Orquestração do pipeline batch disponível atualmente."""

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from banking_data_generator.accounting import (
    calculate_all_account_balances,
    generate_opening_entries,
    sort_ledger_entries,
    validate_ledger,
)
from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    AccountType,
    EntryDirection,
    LedgerEntryType,
)
from banking_data_generator.domain.models import Account, Address, Customer
from banking_data_generator.export import write_batch_csv
from banking_data_generator.generation import (
    generate_accounts,
    generate_addresses,
    generate_card_purchases,
    generate_cards,
    generate_customers,
    generate_internal_transfers,
    generate_merchants,
    generate_purchase_reversals,
)
from banking_data_generator.validation import (
    calculate_net_daily_consumption,
    reconcile_reversal_balances,
    validate_card_purchases,
    validate_cards_and_merchants,
    validate_internal_transfers,
    validate_purchase_reversals,
    validate_transaction_labels,
)


class DatasetValidationError(ValueError):
    """Indica violação de uma invariável antes da escrita batch."""


@dataclass(frozen=True, slots=True)
class BatchPipelineResult:
    """Resumo tipado de uma execução batch concluída."""

    output_directory: Path
    customers_file: Path
    addresses_file: Path
    accounts_file: Path
    cards_file: Path
    merchants_file: Path
    transactions_file: Path
    transaction_labels_file: Path
    transfers_file: Path
    ledger_entries_file: Path
    manifest_file: Path
    customer_count: int
    address_count: int
    account_count: int
    card_count: int
    merchant_count: int
    purchase_attempt_count: int
    approved_transaction_count: int
    declined_transaction_count: int
    target_decline_count: int
    planned_decline_count: int
    additional_decline_count: int
    reversal_target_count: int
    reversal_count: int
    transaction_event_count: int
    reversed_amount_total: Decimal
    final_balance_total: Decimal
    transfer_attempt_count: int
    completed_transfer_count: int
    declined_transfer_count: int
    transfer_target_decline_count: int
    transfer_planned_decline_count: int
    transfer_additional_decline_count: int
    completed_transfer_amount_total: Decimal
    declined_transfer_amount_total: Decimal
    labeled_purchase_count: int
    synthetic_fraud_count: int
    target_fraud_count: int
    approved_fraud_count: int
    declined_fraud_count: int
    fraud_count_by_pattern: dict[str, int]
    ledger_entry_count: int
    opening_credit_total: Decimal
    seed: int
    reference_date: date
    generator_version: str
    schema_version: str
    created: bool
    scenario: str
    quality_target_entity: str
    quality_target_field: str | None
    quality_affected_count: int
    expected_violation_count: int


def run_batch_pipeline(
    config: BankingDataGeneratorConfig,
    project_root: Path,
) -> BatchPipelineResult:
    """Gere, valide e escreva o conjunto batch atual."""
    customers = generate_customers(config)
    addresses = generate_addresses(customers, config)
    accounts = generate_accounts(customers, config)
    merchants = generate_merchants(config)
    cards = generate_cards(accounts, config)

    validate_dataset(config, customers, addresses, accounts)
    validate_cards_and_merchants(config, accounts, cards, merchants)
    purchases = generate_card_purchases(accounts, cards, merchants, config)
    validate_card_purchases(
        config,
        accounts,
        cards,
        merchants,
        purchases.transactions,
        purchases.ledger_entries,
    )
    validate_transaction_labels(
        config, accounts, purchases.transactions, purchases.labels
    )
    reversal_result = generate_purchase_reversals(purchases.transactions, config)
    validate_purchase_reversals(
        config,
        purchases.transactions,
        reversal_result.reversals,
        reversal_result.ledger_entries,
    )
    calculate_net_daily_consumption(
        cards, purchases.transactions, reversal_result.reversals
    )
    transaction_events = sorted(
        [*purchases.transactions, *reversal_result.reversals],
        key=lambda item: (item.effective_at, item.transaction_id),
    )
    pre_transfer_ledger = sort_ledger_entries(
        [
            *generate_opening_entries(accounts),
            *purchases.ledger_entries,
            *reversal_result.ledger_entries,
        ]
    )
    validate_ledger(accounts, pre_transfer_ledger)
    balances_before_transfers = calculate_all_account_balances(
        accounts, pre_transfer_ledger
    )
    reconcile_reversal_balances(
        accounts,
        purchases.transactions,
        reversal_result.reversals,
        balances_before_transfers,
    )
    transfer_result = generate_internal_transfers(
        accounts, balances_before_transfers, transaction_events, config
    )
    expected_balances = validate_internal_transfers(
        config,
        accounts,
        transfer_result.transfers,
        transfer_result.ledger_entries,
        balances_before_transfers,
    )
    ledger_entries = sort_ledger_entries(
        [*pre_transfer_ledger, *transfer_result.ledger_entries]
    )
    validate_ledger(accounts, ledger_entries)
    balances = calculate_all_account_balances(accounts, ledger_entries)
    if balances != expected_balances:
        raise DatasetValidationError(
            "saldos derivados do ledger divergem do efeito das transferências"
        )
    opening_credit_total = sum(
        (
            entry.amount
            for entry in ledger_entries
            if entry.entry_type is LedgerEntryType.OPENING_BALANCE
            and entry.direction is EntryDirection.CREDIT
        ),
        Decimal("0.00"),
    )
    publication = write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        ledger_entries,
        cards=cards,
        merchants=merchants,
        transactions=transaction_events,
        transaction_labels=purchases.labels,
        transfers=transfer_result.transfers,
        project_root=project_root,
    )
    quality_manifest = json.loads(
        publication.paths.manifest.read_text(encoding="utf-8")
    )["quality_summary"]
    return BatchPipelineResult(
        output_directory=publication.paths.directory,
        customers_file=publication.paths.customers,
        addresses_file=publication.paths.addresses,
        accounts_file=publication.paths.accounts,
        cards_file=publication.paths.cards,
        merchants_file=publication.paths.merchants,
        transactions_file=publication.paths.transactions,
        transaction_labels_file=publication.paths.transaction_labels,
        transfers_file=publication.paths.transfers,
        ledger_entries_file=publication.paths.ledger_entries,
        manifest_file=publication.paths.manifest,
        customer_count=len(customers),
        address_count=len(addresses),
        account_count=len(accounts),
        card_count=len(cards),
        merchant_count=len(merchants),
        purchase_attempt_count=len(purchases.transactions),
        approved_transaction_count=sum(
            transaction.status.value == "approved"
            for transaction in purchases.transactions
        ),
        declined_transaction_count=sum(
            transaction.status.value == "declined"
            for transaction in purchases.transactions
        ),
        target_decline_count=purchases.target_declines,
        planned_decline_count=purchases.planned_declines,
        additional_decline_count=purchases.additional_declines,
        reversal_target_count=reversal_result.target_reversals,
        reversal_count=len(reversal_result.reversals),
        transaction_event_count=len(transaction_events),
        reversed_amount_total=sum(
            (item.amount for item in reversal_result.reversals), Decimal("0.00")
        ),
        final_balance_total=sum(balances.values(), Decimal("0.00")),
        transfer_attempt_count=len(transfer_result.transfers),
        completed_transfer_count=sum(
            item.status.value == "completed" for item in transfer_result.transfers
        ),
        declined_transfer_count=sum(
            item.status.value == "declined" for item in transfer_result.transfers
        ),
        transfer_target_decline_count=transfer_result.target_declines,
        transfer_planned_decline_count=transfer_result.planned_declines,
        transfer_additional_decline_count=transfer_result.additional_declines,
        completed_transfer_amount_total=sum(
            (
                item.amount
                for item in transfer_result.transfers
                if item.status.value == "completed"
            ),
            Decimal("0.00"),
        ),
        declined_transfer_amount_total=sum(
            (
                item.amount
                for item in transfer_result.transfers
                if item.status.value == "declined"
            ),
            Decimal("0.00"),
        ),
        labeled_purchase_count=len(purchases.labels),
        synthetic_fraud_count=sum(
            label.is_synthetic_fraud for label in purchases.labels
        ),
        target_fraud_count=purchases.target_fraud_count,
        approved_fraud_count=sum(
            label.is_synthetic_fraud and transaction.status.value == "approved"
            for label, transaction in zip(
                purchases.labels, purchases.transactions, strict=True
            )
        ),
        declined_fraud_count=sum(
            label.is_synthetic_fraud and transaction.status.value == "declined"
            for label, transaction in zip(
                purchases.labels, purchases.transactions, strict=True
            )
        ),
        fraud_count_by_pattern=dict(
            Counter(
                label.risk_pattern.value
                for label in purchases.labels
                if label.risk_pattern is not None
            )
        ),
        ledger_entry_count=len(ledger_entries),
        opening_credit_total=opening_credit_total,
        seed=config.seed,
        reference_date=config.reference_date,
        generator_version=publication.generator_version,
        schema_version=publication.schema_version,
        created=publication.created,
        scenario=config.quality.scenario,
        quality_target_entity=quality_manifest["target_entity"],
        quality_target_field=quality_manifest["target_field"],
        quality_affected_count=quality_manifest["affected_count"],
        expected_violation_count=quality_manifest["expected_violation_count"],
    )


def validate_dataset(
    config: BankingDataGeneratorConfig,
    customers: Sequence[Customer],
    addresses: Sequence[Address],
    accounts: Sequence[Account],
) -> None:
    """Valide invariantes que abrangem o conjunto completo gerado."""
    _validate_unique_ids((customer.customer_id for customer in customers), "clientes")
    _validate_unique_ids((address.address_id for address in addresses), "endereços")
    _validate_unique_ids((account.account_id for account in accounts), "contas")

    customer_ids = {customer.customer_id for customer in customers}
    orphan_addresses = {
        address.customer_id
        for address in addresses
        if address.customer_id not in customer_ids
    }
    if orphan_addresses:
        _fail("existem endereços que referenciam clientes inexistentes")

    primary_counts = Counter(
        address.customer_id for address in addresses if address.is_primary
    )
    if any(primary_counts[customer_id] != 1 for customer_id in customer_ids):
        _fail("cada cliente deve possuir exatamente um endereço principal")

    orphan_accounts = {
        account.customer_id
        for account in accounts
        if account.customer_id not in customer_ids
    }
    if orphan_accounts:
        _fail("existem contas que referenciam clientes inexistentes")

    account_counts = Counter(account.customer_id for account in accounts)
    for customer_id in customer_ids:
        count = account_counts[customer_id]
        if (
            not config.accounts.min_per_customer
            <= count
            <= config.accounts.max_per_customer
        ):
            _fail(
                "a quantidade de contas por cliente está fora dos limites configurados"
            )

    allowed_types = set(AccountType)
    if any(account.account_type not in allowed_types for account in accounts):
        _fail("existe conta com tipo não permitido")
    if any(account.currency != config.currency for account in accounts):
        _fail("existe conta com moeda diferente da configuração")
    for account in accounts:
        if not isinstance(account.opening_balance, Decimal):
            _fail("todo saldo de abertura deve usar Decimal")
        if not (
            config.accounts.initial_balance.min
            <= account.opening_balance
            <= config.accounts.initial_balance.max
        ):
            _fail("existe saldo de abertura fora dos limites configurados")


def _validate_unique_ids(identifiers: Iterable[str], entity_name: str) -> None:
    values = list(identifiers)
    if len(values) != len(set(values)):
        _fail(f"IDs de {entity_name} devem ser únicos")


def _fail(message: str) -> None:
    raise DatasetValidationError(f"Conjunto gerado inválido: {message}.")
