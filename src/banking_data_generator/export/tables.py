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
    Transaction,
    TransactionLabel,
    Transfer,
)
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CARD_SCHEMA,
    CUSTOMER_SCHEMA,
    LEDGER_ENTRY_SCHEMA,
    MERCHANT_SCHEMA,
    TRANSACTION_LABEL_SCHEMA,
    TRANSACTION_SCHEMA,
    TRANSFER_SCHEMA,
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


def transactions_to_table(transactions: Sequence[Transaction]) -> pa.Table:
    records = [
        {
            "transaction_id": transaction.transaction_id,
            "account_id": transaction.account_id,
            "card_id": transaction.card_id,
            "merchant_id": transaction.merchant_id,
            "transaction_type": transaction.transaction_type.value,
            "status": transaction.status.value,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "effective_at": transaction.effective_at,
            "event_at": transaction.event_at,
            "ingested_at": transaction.ingested_at,
            "decline_reason": (
                transaction.decline_reason.value if transaction.decline_reason else None
            ),
            "original_transaction_id": transaction.original_transaction_id,
        }
        for transaction in transactions
    ]
    return pa.Table.from_pylist(records, schema=TRANSACTION_SCHEMA)


def transaction_labels_to_table(labels: Sequence[TransactionLabel]) -> pa.Table:
    """Converta o ground truth separado na ordem do contrato público."""
    records = [
        {
            "transaction_id": label.transaction_id,
            "is_synthetic_fraud": label.is_synthetic_fraud,
            "risk_pattern": label.risk_pattern.value if label.risk_pattern else None,
            "risk_score": label.risk_score,
            "label_version": label.label_version,
        }
        for label in labels
    ]
    return pa.Table.from_pylist(records, schema=TRANSACTION_LABEL_SCHEMA)


def transfers_to_table(transfers: Sequence[Transfer]) -> pa.Table:
    """Converta transferências sem transformar valores monetários em float."""
    records = [
        {
            "transfer_id": transfer.transfer_id,
            "source_account_id": transfer.source_account_id,
            "destination_account_id": transfer.destination_account_id,
            "transfer_type": transfer.transfer_type.value,
            "status": transfer.status.value,
            "amount": transfer.amount,
            "currency": transfer.currency,
            "effective_at": transfer.effective_at,
            "event_at": transfer.event_at,
            "ingested_at": transfer.ingested_at,
            "decline_reason": (
                transfer.decline_reason.value if transfer.decline_reason else None
            ),
        }
        for transfer in transfers
    ]
    return pa.Table.from_pylist(records, schema=TRANSFER_SCHEMA)
