"""Orquestração do pipeline batch disponível atualmente."""

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
    generate_merchants,
)
from banking_data_generator.validation import (
    reconcile_purchase_balances,
    validate_card_purchases,
    validate_cards_and_merchants,
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
    ledger_entries_file: Path
    manifest_file: Path
    customer_count: int
    address_count: int
    account_count: int
    card_count: int
    merchant_count: int
    transaction_count: int
    approved_transaction_count: int
    declined_transaction_count: int
    target_decline_count: int
    planned_decline_count: int
    additional_decline_count: int
    ledger_entry_count: int
    opening_credit_total: Decimal
    seed: int
    reference_date: date
    generator_version: str
    schema_version: str
    created: bool


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
    ledger_entries = sort_ledger_entries(
        [*generate_opening_entries(accounts), *purchases.ledger_entries]
    )
    validate_ledger(accounts, ledger_entries)
    balances = calculate_all_account_balances(accounts, ledger_entries)
    reconcile_purchase_balances(accounts, purchases.transactions, balances)
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
        transactions=purchases.transactions,
        project_root=project_root,
    )
    return BatchPipelineResult(
        output_directory=publication.paths.directory,
        customers_file=publication.paths.customers,
        addresses_file=publication.paths.addresses,
        accounts_file=publication.paths.accounts,
        cards_file=publication.paths.cards,
        merchants_file=publication.paths.merchants,
        transactions_file=publication.paths.transactions,
        ledger_entries_file=publication.paths.ledger_entries,
        manifest_file=publication.paths.manifest,
        customer_count=len(customers),
        address_count=len(addresses),
        account_count=len(accounts),
        card_count=len(cards),
        merchant_count=len(merchants),
        transaction_count=len(purchases.transactions),
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
        ledger_entry_count=len(ledger_entries),
        opening_credit_total=opening_credit_total,
        seed=config.seed,
        reference_date=config.reference_date,
        generator_version=publication.generator_version,
        schema_version=publication.schema_version,
        created=publication.created,
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
