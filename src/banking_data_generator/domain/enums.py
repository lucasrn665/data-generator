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
    CARD_PURCHASE = "card_purchase"
    CARD_PURCHASE_REVERSAL = "card_purchase_reversal"


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


class TransactionType(StrEnum):
    CARD_PURCHASE = "card_purchase"
    CARD_PURCHASE_REVERSAL = "card_purchase_reversal"


class TransactionStatus(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"
    COMPLETED = "completed"


class DeclineReason(StrEnum):
    CARD_BLOCKED = "card_blocked"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    DAILY_LIMIT_EXCEEDED = "daily_limit_exceeded"
    MERCHANT_INACTIVE = "merchant_inactive"
    SYNTHETIC_RISK_RULE = "synthetic_risk_rule"
