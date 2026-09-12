"""Modelos e contratos do domínio bancário sintético."""

from banking_data_generator.domain.enums import (
    AccountType,
    ActivityProfile,
    EntityStatus,
)
from banking_data_generator.domain.models import Account, Address, Customer
from banking_data_generator.domain.schemas import (
    ACCOUNT_SCHEMA,
    ADDRESS_SCHEMA,
    CUSTOMER_SCHEMA,
)

__all__ = [
    "ACCOUNT_SCHEMA",
    "ADDRESS_SCHEMA",
    "CUSTOMER_SCHEMA",
    "Account",
    "AccountType",
    "ActivityProfile",
    "Address",
    "Customer",
    "EntityStatus",
]
