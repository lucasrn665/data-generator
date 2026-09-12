"""Geração determinística de clientes sintéticos."""

from datetime import timedelta

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import ActivityProfile, EntityStatus
from banking_data_generator.domain.models import Customer
from banking_data_generator.generation.context import GenerationContext

_ACTIVITY_PROFILES = tuple(ActivityProfile)
_STATUSES = tuple(EntityStatus)


def generate_customers(config: BankingDataGeneratorConfig) -> list[Customer]:
    """Gere clientes sintéticos reproduzíveis para a configuração recebida."""
    context = GenerationContext.create(config.seed, "customers")
    customers: list[Customer] = []

    for index in range(1, config.customers.count + 1):
        customer_id = f"SYN-CUS-{index:010d}"
        age_days = context.random.randint(18 * 365, 90 * 365)
        created_days_ago = context.random.randint(0, 10 * 365)
        customers.append(
            Customer(
                customer_id=customer_id,
                synthetic_name=context.faker.name(),
                birth_date=config.reference_date - timedelta(days=age_days),
                synthetic_email=(
                    f"customer-{index:010d}-{config.seed}@example.invalid"
                ),
                created_date=config.reference_date - timedelta(days=created_days_ago),
                activity_profile=context.random.choice(_ACTIVITY_PROFILES),
                status=context.random.choice(_STATUSES),
            )
        )

    return customers
