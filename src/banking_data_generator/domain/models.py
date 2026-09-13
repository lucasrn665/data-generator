"""Modelos tipados e imutáveis do domínio inicial."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from banking_data_generator.domain.enums import (
    AccountType,
    ActivityProfile,
    CardStatus,
    CardType,
    EntityStatus,
    EntryDirection,
    LedgerEntryType,
    MerchantCategory,
    MerchantRiskProfile,
    MerchantStatus,
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


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """Lançamento imutável do subledger de contas dos clientes."""

    entry_id: str
    account_id: str
    entry_type: LedgerEntryType
    direction: EntryDirection
    amount: Decimal
    currency: str
    effective_at: datetime
    reference_id: str
    sequence_number: int


@dataclass(frozen=True, slots=True)
class Merchant:
    """Estabelecimento inteiramente sintético e sem identificador oficial."""

    merchant_id: str
    synthetic_name: str
    category: MerchantCategory
    category_code: str
    city: str
    state: str
    country: str
    risk_profile: MerchantRiskProfile
    created_date: date
    status: MerchantStatus


@dataclass(frozen=True, slots=True)
class DebitCard:
    """Cartão sintético sem PAN, CVV ou credencial bancária."""

    card_id: str
    account_id: str
    card_type: CardType
    status: CardStatus
    issued_date: date
    expiration_date: date
    daily_purchase_limit: Decimal
    currency: str
