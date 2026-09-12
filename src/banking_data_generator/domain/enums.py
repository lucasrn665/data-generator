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
