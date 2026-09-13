"""Validação conjunta de cartões e estabelecimentos sintéticos."""

from collections import Counter
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import (
    MERCHANT_CATEGORY_CODES,
    CardStatus,
    CardType,
    MerchantRiskProfile,
    MerchantStatus,
)
from banking_data_generator.domain.models import Account, DebitCard, Merchant


class ExtendedDomainValidationError(ValueError):
    """Indica violação nas entidades adicionadas ao domínio."""


def validate_cards_and_merchants(
    config: BankingDataGeneratorConfig,
    accounts: Sequence[Account],
    cards: Sequence[DebitCard],
    merchants: Sequence[Merchant],
) -> None:
    """Valide cardinalidade, relacionamentos e valores das novas entidades."""
    _unique_prefixed((card.card_id for card in cards), "SYN-CRD-", "cartão")
    _unique_prefixed(
        (merchant.merchant_id for merchant in merchants), "SYN-MER-", "estabelecimento"
    )
    if len(merchants) != config.merchants.count:
        _fail("quantidade de estabelecimentos divergente da configuração")

    account_by_id = {account.account_id: account for account in accounts}
    for card in cards:
        account = account_by_id.get(card.account_id)
        if account is None:
            _fail(f"cartão '{card.card_id}' referencia conta inexistente")
        if card.card_type is not CardType.DEBIT:
            _fail(f"tipo inválido no cartão '{card.card_id}'")
        if not isinstance(card.status, CardStatus):
            _fail(f"status inválido no cartão '{card.card_id}'")
        if card.currency != account.currency:
            _fail(f"moeda divergente no cartão '{card.card_id}'")
        if not isinstance(card.daily_purchase_limit, Decimal):
            _fail(f"limite do cartão '{card.card_id}' deve usar Decimal")
        if card.daily_purchase_limit <= 0:
            _fail(f"limite do cartão '{card.card_id}' deve ser positivo")
        if card.daily_purchase_limit.as_tuple().exponent != -2:
            _fail(f"limite do cartão '{card.card_id}' deve ter escala 2")
        if not (
            config.cards.daily_purchase_limit.min
            <= card.daily_purchase_limit
            <= config.cards.daily_purchase_limit.max
        ):
            _fail(f"limite do cartão '{card.card_id}' fora da configuração")
        if card.issued_date > config.reference_date:
            _fail(f"emissão futura no cartão '{card.card_id}'")
        if card.expiration_date <= card.issued_date:
            _fail(f"expiração inválida no cartão '{card.card_id}'")

    counts = Counter(card.account_id for card in cards)
    for account in accounts:
        if counts[account.account_id] != config.cards.per_account:
            _fail(f"quantidade de cartões inválida na conta '{account.account_id}'")

    expected_blocked = int(
        (Decimal(len(cards)) * config.cards.initially_blocked_rate).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    actual_blocked = sum(card.status is CardStatus.BLOCKED for card in cards)
    if actual_blocked != expected_blocked:
        _fail("quantidade de cartões bloqueados divergente da taxa configurada")

    for merchant in merchants:
        if MERCHANT_CATEGORY_CODES.get(merchant.category) != merchant.category_code:
            _fail(f"categoria incoerente no estabelecimento '{merchant.merchant_id}'")
        if not isinstance(merchant.risk_profile, MerchantRiskProfile):
            _fail(f"risco inválido no estabelecimento '{merchant.merchant_id}'")
        if not isinstance(merchant.status, MerchantStatus):
            _fail(f"status inválido no estabelecimento '{merchant.merchant_id}'")
        if merchant.created_date > config.reference_date:
            _fail(f"criação futura no estabelecimento '{merchant.merchant_id}'")


def _unique_prefixed(values: object, prefix: str, entity: str) -> None:
    identifiers = list(values)
    if len(identifiers) != len(set(identifiers)):
        _fail(f"IDs de {entity} devem ser únicos")
    if any(not value.startswith(prefix) for value in identifiers):
        _fail(f"ID de {entity} sem prefixo sintético '{prefix}'")


def _fail(message: str) -> None:
    raise ExtendedDomainValidationError(f"Domínio estendido inválido: {message}.")
