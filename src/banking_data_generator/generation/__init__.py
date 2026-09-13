"""Geração determinística do domínio bancário sintético."""

from banking_data_generator.generation.accounts import generate_accounts
from banking_data_generator.generation.addresses import generate_addresses
from banking_data_generator.generation.cards import generate_cards
from banking_data_generator.generation.customers import generate_customers
from banking_data_generator.generation.merchants import generate_merchants
from banking_data_generator.generation.reversals import (
    ReversalGenerationResult,
    calculate_reversal_target,
    generate_purchase_reversals,
)
from banking_data_generator.generation.transactions import (
    PurchaseGenerationResult,
    calculate_fraud_target,
    fraud_pattern_plan,
    generate_card_purchases,
)
from banking_data_generator.generation.transfers import (
    TransferGenerationError,
    TransferGenerationResult,
    generate_internal_transfers,
)

__all__ = [
    "generate_accounts",
    "generate_addresses",
    "generate_cards",
    "generate_customers",
    "generate_merchants",
    "generate_card_purchases",
    "PurchaseGenerationResult",
    "calculate_fraud_target",
    "fraud_pattern_plan",
    "ReversalGenerationResult",
    "calculate_reversal_target",
    "generate_purchase_reversals",
    "TransferGenerationError",
    "TransferGenerationResult",
    "generate_internal_transfers",
]
