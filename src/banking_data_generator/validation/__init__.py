"""Validações que abrangem múltiplas entidades do domínio."""

from banking_data_generator.validation.cards_merchants import (
    ExtendedDomainValidationError,
    validate_cards_and_merchants,
)

__all__ = ["ExtendedDomainValidationError", "validate_cards_and_merchants"]
