"""Geração determinística de endereços sintéticos."""

from collections.abc import Sequence

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.models import Address, Customer
from banking_data_generator.generation.context import GenerationContext


def generate_addresses(
    customers: Sequence[Customer], config: BankingDataGeneratorConfig
) -> list[Address]:
    """Gere exatamente um endereço principal para cada cliente."""
    context = GenerationContext.create(config.seed, "addresses")
    addresses: list[Address] = []

    for index, customer in enumerate(customers, start=1):
        complement = None
        if context.random.random() < 0.35:
            complement = f"Unidade sintética {context.random.randint(1, 999)}"
        addresses.append(
            Address(
                address_id=f"SYN-ADR-{index:010d}",
                customer_id=customer.customer_id,
                street=context.faker.street_name(),
                number=f"SYN-NUM-{context.random.randint(1, 99999):05d}",
                complement=complement,
                neighborhood=context.faker.bairro(),
                city=context.faker.city(),
                state=context.faker.estado_sigla(),
                synthetic_postal_code=f"SYN-POST-{index:010d}",
                country="Brasil",
                is_primary=True,
            )
        )

    return addresses
