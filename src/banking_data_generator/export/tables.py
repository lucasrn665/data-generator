"""Conversões explícitas dos modelos de domínio para tabelas PyArrow."""

from collections.abc import Sequence

import pyarrow as pa

from banking_data_generator.domain.models import Account, Address, Customer
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CUSTOMER_SCHEMA,
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
