"""Orquestração do pipeline batch disponível atualmente."""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import AccountType
from banking_data_generator.domain.models import Account, Address, Customer
from banking_data_generator.export import write_batch_csv
from banking_data_generator.generation import (
    generate_accounts,
    generate_addresses,
    generate_customers,
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
    customer_count: int
    address_count: int
    account_count: int
    seed: int
    reference_date: date


def run_batch_pipeline(
    config: BankingDataGeneratorConfig,
    project_root: Path,
) -> BatchPipelineResult:
    """Gere, valide e escreva o conjunto batch atual."""
    customers = generate_customers(config)
    addresses = generate_addresses(customers, config)
    accounts = generate_accounts(customers, config)

    validate_dataset(config, customers, addresses, accounts)
    paths = write_batch_csv(
        config,
        customers,
        addresses,
        accounts,
        project_root=project_root,
    )
    return BatchPipelineResult(
        output_directory=paths.directory,
        customers_file=paths.customers,
        addresses_file=paths.addresses,
        accounts_file=paths.accounts,
        customer_count=len(customers),
        address_count=len(addresses),
        account_count=len(accounts),
        seed=config.seed,
        reference_date=config.reference_date,
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
