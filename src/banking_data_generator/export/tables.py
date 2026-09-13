"""Conversões explícitas dos modelos de domínio para tabelas PyArrow."""

from collections.abc import Sequence

import pyarrow as pa

from banking_data_generator.domain.models import (
    Account,
    Address,
    Customer,
    DebitCard,
    LedgerEntry,
    Merchant,
)
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CARD_SCHEMA,
    CUSTOMER_SCHEMA,
    LEDGER_ENTRY_SCHEMA,
    MERCHANT_SCHEMA,
)


def customers_to_table(customers: Sequence[Customer]) -> pa.Table:
    """Converta clientes para a ordem e os tipos do schema público."""
    records = [
        {
            "customer_id": customer.customer_id,
            "synthetic_name": customer.synthetic_name,
            "birth_date": customer.birth_date,
            "synthetic_email": customer.synthetic_email,
            "created_date": customer.created_date,
            "activity_profile": customer.activity_profile.value,
            "status": customer.status.value,
        }
        for customer in customers
    ]
    return pa.Table.from_pylist(records, schema=CUSTOMER_SCHEMA)


def addresses_to_table(addresses: Sequence[Address]) -> pa.Table:
    """Converta endereços para a ordem e os tipos do schema público."""
    records = [
        {
            "address_id": address.address_id,
            "customer_id": address.customer_id,
            "street": address.street,
            "number": address.number,
            "complement": address.complement,
            "neighborhood": address.neighborhood,
            "city": address.city,
            "state": address.state,
            "synthetic_postal_code": address.synthetic_postal_code,
            "country": address.country,
            "is_primary": address.is_primary,
        }
        for address in addresses
    ]
    return pa.Table.from_pylist(records, schema=ADDRESS_SCHEMA)


def accounts_to_table(accounts: Sequence[Account]) -> pa.Table:
    """Converta contas sem transformar valores monetários em float."""
    records = [
        {
            "account_id": account.account_id,
            "customer_id": account.customer_id,
            "account_type": account.account_type.value,
            "currency": account.currency,
            "opening_balance": account.opening_balance,
            "opened_date": account.opened_date,
            "status": account.status.value,
        }
        for account in accounts
    ]
    return pa.Table.from_pylist(records, schema=ACCOUNT_SCHEMA)


def ledger_entries_to_table(entries: Sequence[LedgerEntry]) -> pa.Table:
    """Converta lançamentos em memória sem iniciar sua exportação CSV."""
    records = [
        {
            "entry_id": entry.entry_id,
            "account_id": entry.account_id,
            "entry_type": entry.entry_type.value,
            "direction": entry.direction.value,
            "amount": entry.amount,
            "currency": entry.currency,
            "effective_at": entry.effective_at,
            "reference_id": entry.reference_id,
            "sequence_number": entry.sequence_number,
        }
        for entry in entries
    ]
    return pa.Table.from_pylist(records, schema=LEDGER_ENTRY_SCHEMA)


def cards_to_table(cards: Sequence[DebitCard]) -> pa.Table:
    """Converta cartões sem introduzir números ou credenciais bancárias."""
    records = [
        {
            "card_id": card.card_id,
            "account_id": card.account_id,
            "card_type": card.card_type.value,
            "status": card.status.value,
            "issued_date": card.issued_date,
            "expiration_date": card.expiration_date,
            "daily_purchase_limit": card.daily_purchase_limit,
            "currency": card.currency,
        }
        for card in cards
    ]
    return pa.Table.from_pylist(records, schema=CARD_SCHEMA)


def merchants_to_table(merchants: Sequence[Merchant]) -> pa.Table:
    """Converta estabelecimentos na ordem do contrato batch."""
    records = [
        {
            "merchant_id": merchant.merchant_id,
            "synthetic_name": merchant.synthetic_name,
            "category": merchant.category.value,
            "category_code": merchant.category_code,
            "city": merchant.city,
            "state": merchant.state,
            "country": merchant.country,
            "risk_profile": merchant.risk_profile.value,
            "created_date": merchant.created_date,
            "status": merchant.status.value,
        }
        for merchant in merchants
    ]
    return pa.Table.from_pylist(records, schema=MERCHANT_SCHEMA)
