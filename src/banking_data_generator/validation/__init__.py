"""Validações que abrangem múltiplas entidades do domínio."""

from banking_data_generator.validation.cards_merchants import (
    ExtendedDomainValidationError,
    validate_cards_and_merchants,
)
from banking_data_generator.validation.purchases import (
    TransactionValidationError,
    reconcile_purchase_balances,
    validate_card_purchases,
)
from banking_data_generator.validation.reversals import (
    ReversalValidationError,
    calculate_net_daily_consumption,
    reconcile_reversal_balances,
    validate_purchase_reversals,
)

__all__ = [
    "ExtendedDomainValidationError",
    "TransactionValidationError",
    "ReversalValidationError",
    "calculate_net_daily_consumption",
    "reconcile_purchase_balances",
    "reconcile_reversal_balances",
    "validate_card_purchases",
    "validate_cards_and_merchants",
    "validate_purchase_reversals",
]
