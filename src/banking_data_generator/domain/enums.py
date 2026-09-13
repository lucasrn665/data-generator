"""Valores enumerados do domínio inicial."""

from enum import StrEnum


class ActivityProfile(StrEnum):
    """Perfil sintético de atividade de um cliente."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EntityStatus(StrEnum):
    """Status inicial compartilhado por clientes e contas."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class AccountType(StrEnum):
    """Tipos de conta admitidos na primeira versão."""

    CHECKING = "checking"
    SAVINGS = "savings"


class LedgerEntryType(StrEnum):
    """Tipos de lançamento admitidos no subledger atual."""

    OPENING_BALANCE = "opening_balance"


class EntryDirection(StrEnum):
    """Direção contábil explícita de um lançamento."""

    CREDIT = "credit"
    DEBIT = "debit"


class CardType(StrEnum):
    """Tipos de cartão permitidos no contrato atual."""

    DEBIT = "debit"


class CardStatus(StrEnum):
    """Estados iniciais de um cartão sintético."""

    ACTIVE = "active"
    BLOCKED = "blocked"


class MerchantCategory(StrEnum):
    """Categorias fechadas de estabelecimentos sintéticos."""

    GROCERY = "grocery"
    RESTAURANT = "restaurant"
    PHARMACY = "pharmacy"
    FUEL = "fuel"
    RETAIL = "retail"


class MerchantRiskProfile(StrEnum):
    """Perfis sintéticos de risco de estabelecimento."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MerchantStatus(StrEnum):
    """Estados de um estabelecimento sintético."""

    ACTIVE = "active"
    INACTIVE = "inactive"


MERCHANT_CATEGORY_CODES: dict[MerchantCategory, str] = {
    MerchantCategory.GROCERY: "SYN-MCC-GROCERY",
    MerchantCategory.RESTAURANT: "SYN-MCC-RESTAURANT",
    MerchantCategory.PHARMACY: "SYN-MCC-PHARMACY",
    MerchantCategory.FUEL: "SYN-MCC-FUEL",
    MerchantCategory.RETAIL: "SYN-MCC-RETAIL",
}
