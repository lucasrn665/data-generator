"""Geração determinística de estabelecimentos inteiramente sintéticos."""

from datetime import timedelta

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    MERCHANT_CATEGORY_CODES,
    MerchantCategory,
    MerchantRiskProfile,
    MerchantStatus,
)
from banking_data_generator.domain.models import Merchant
from banking_data_generator.generation.context import GenerationContext

_CATEGORIES = tuple(MerchantCategory)
_RISK_PROFILES = tuple(MerchantRiskProfile)
_STATUSES = tuple(MerchantStatus)


def generate_merchants(config: BankingDataGeneratorConfig) -> list[Merchant]:
    """Gere estabelecimentos sem CNPJ ou qualquer identificador oficial."""
    context = GenerationContext.create(config.seed, "merchants")
    merchants: list[Merchant] = []
    for index in range(1, config.merchants.count + 1):
        category = context.random.choice(_CATEGORIES)
        merchants.append(
            Merchant(
                merchant_id=f"SYN-MER-{index:010d}",
                synthetic_name=f"Estabelecimento Sintético {context.faker.company()}",
                category=category,
                category_code=MERCHANT_CATEGORY_CODES[category],
                city=context.faker.city(),
                state=context.faker.estado_sigla(),
                country="Brasil",
                risk_profile=context.random.choice(_RISK_PROFILES),
                created_date=config.reference_date
                - timedelta(days=context.random.randint(0, 10 * 365)),
                status=context.random.choice(_STATUSES),
            )
        )
    return merchants
