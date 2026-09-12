"""Modelos tipados e imutáveis do domínio inicial."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from banking_data_generator.domain.enums import (
    AccountType,
    ActivityProfile,
    EntityStatus,
)


@dataclass(frozen=True, slots=True)
class Customer:
    """Cliente inteiramente sintético."""

    customer_id: str
    synthetic_name: str
    birth_date: date
    synthetic_email: str
    created_date: date
    activity_profile: ActivityProfile
    status: EntityStatus


@dataclass(frozen=True, slots=True)
class Address:
    """Endereço inteiramente sintético associado a um cliente."""

    address_id: str
    customer_id: str
    street: str
    number: str
    complement: str | None
    neighborhood: str
    city: str
    state: str
    synthetic_postal_code: str
    country: str
    is_primary: bool


@dataclass(frozen=True, slots=True)
class Account:
    """Conta bancária inteiramente sintética."""

    account_id: str
    customer_id: str
    account_type: AccountType
    currency: str
    opening_balance: Decimal
    opened_date: date
    status: EntityStatus
