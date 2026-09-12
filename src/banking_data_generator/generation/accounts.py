"""Geração determinística de contas bancárias sintéticas."""

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import AccountType, EntityStatus
from banking_data_generator.domain.models import Account, Customer
from banking_data_generator.generation.context import GenerationContext

_ACCOUNT_TYPES = tuple(AccountType)
_STATUSES = tuple(EntityStatus)
_CENTS_PER_UNIT = Decimal("100")
_CENT = Decimal("0.01")


def generate_accounts(
    customers: Sequence[Customer], config: BankingDataGeneratorConfig
) -> list[Account]:
    """Gere contas válidas e reproduzíveis para os clientes recebidos."""
    context = GenerationContext.create(config.seed, "accounts")
    minimum_cents = int(config.accounts.initial_balance.min * _CENTS_PER_UNIT)
    maximum_cents = int(config.accounts.initial_balance.max * _CENTS_PER_UNIT)
    accounts: list[Account] = []

    for customer in customers:
        count = context.random.randint(
            config.accounts.min_per_customer,
            config.accounts.max_per_customer,
        )
        for _ in range(count):
            index = len(accounts) + 1
            balance_cents = context.random.randint(minimum_cents, maximum_cents)
            accounts.append(
                Account(
                    account_id=f"SYN-ACC-{index:012d}",
                    customer_id=customer.customer_id,
                    account_type=context.random.choice(_ACCOUNT_TYPES),
                    currency=config.currency,
                    opening_balance=(Decimal(balance_cents) / _CENTS_PER_UNIT).quantize(
                        _CENT
                    ),
                    opened_date=config.reference_date
                    - timedelta(days=context.random.randint(0, 10 * 365)),
                    status=context.random.choice(_STATUSES),
                )
            )

    return accounts
