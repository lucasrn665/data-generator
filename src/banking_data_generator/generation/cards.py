"""Geração determinística de cartões de débito sem credenciais bancárias."""

from collections.abc import Sequence
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import CardStatus, CardType
from banking_data_generator.domain.models import Account, DebitCard
from banking_data_generator.generation.context import GenerationContext

_CENTS_PER_UNIT = Decimal("100")
_CENT = Decimal("0.01")


def generate_cards(
    accounts: Sequence[Account], config: BankingDataGeneratorConfig
) -> list[DebitCard]:
    """Gere cartões vinculados a contas, sem PAN, CVV, senha ou trilha."""
    context = GenerationContext.create(config.seed, "cards")
    cards: list[DebitCard] = []
    minimum_cents = int(config.cards.daily_purchase_limit.min * _CENTS_PER_UNIT)
    maximum_cents = int(config.cards.daily_purchase_limit.max * _CENTS_PER_UNIT)

    for account in accounts:
        for _ in range(config.cards.per_account):
            index = len(cards) + 1
            issued_date = account.opened_date + timedelta(
                days=context.random.randint(
                    0, (config.reference_date - account.opened_date).days
                )
            )
            cards.append(
                DebitCard(
                    card_id=f"SYN-CRD-{index:012d}",
                    account_id=account.account_id,
                    card_type=CardType.DEBIT,
                    status=CardStatus.ACTIVE,
                    issued_date=issued_date,
                    expiration_date=issued_date
                    + timedelta(days=context.random.randint(3 * 365, 5 * 365)),
                    daily_purchase_limit=(
                        Decimal(context.random.randint(minimum_cents, maximum_cents))
                        / _CENTS_PER_UNIT
                    ).quantize(_CENT),
                    currency=account.currency,
                )
            )

    blocked_count = int(
        (Decimal(len(cards)) * config.cards.initially_blocked_rate).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    blocked_indexes = set(context.random.sample(range(len(cards)), blocked_count))
    return [
        DebitCard(
            card_id=card.card_id,
            account_id=card.account_id,
            card_type=card.card_type,
            status=(
                CardStatus.BLOCKED if index in blocked_indexes else CardStatus.ACTIVE
            ),
            issued_date=card.issued_date,
            expiration_date=card.expiration_date,
            daily_purchase_limit=card.daily_purchase_limit,
            currency=card.currency,
        )
        for index, card in enumerate(cards)
    ]
