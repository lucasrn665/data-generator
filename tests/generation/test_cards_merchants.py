from collections import Counter
from dataclasses import fields, replace
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pyarrow as pa
import pytest

from banking_data_generator.config import BankingDataGeneratorConfig, load_config
from banking_data_generator.domain.enums import (
    MERCHANT_CATEGORY_CODES,
    CardStatus,
    CardType,
)
from banking_data_generator.domain.models import DebitCard, Merchant
from banking_data_generator.domain.schemas import CARD_SCHEMA, MERCHANT_SCHEMA
from banking_data_generator.export import cards_to_table, merchants_to_table
from banking_data_generator.generation import (
    generate_accounts,
    generate_cards,
    generate_customers,
    generate_merchants,
)
from banking_data_generator.validation import (
    ExtendedDomainValidationError,
    validate_cards_and_merchants,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def domain() -> tuple[BankingDataGeneratorConfig, list, list, list]:
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        customers=replace(config.customers, count=20),
        merchants=replace(config.merchants, count=25),
        cards=replace(config.cards, per_account=2),
    )
    accounts = generate_accounts(generate_customers(config), config)
    return (
        config,
        accounts,
        generate_cards(accounts, config),
        generate_merchants(config),
    )


def test_generation_is_deterministic_and_seed_isolated(domain: tuple) -> None:
    config, accounts, cards, merchants = domain
    assert generate_cards(accounts, config) == cards
    assert generate_merchants(config) == merchants

    other = replace(config, seed=config.seed + 1)
    assert generate_cards(accounts, other) != cards
    assert generate_merchants(other) != merchants

    changed_merchants = replace(config, merchants=replace(config.merchants, count=3))
    assert generate_cards(accounts, changed_merchants) == cards
    changed_cards = replace(config, cards=replace(config.cards, per_account=1))
    assert generate_merchants(changed_cards) == merchants


def test_cards_have_valid_ids_relationships_cardinality_and_no_credentials(
    domain: tuple,
) -> None:
    config, accounts, cards, _ = domain
    account_ids = {account.account_id for account in accounts}
    identifiers = [card.card_id for card in cards]

    assert len(identifiers) == len(set(identifiers))
    assert all(value.startswith("SYN-CRD-") for value in identifiers)
    assert {card.account_id for card in cards} <= account_ids
    assert Counter(card.account_id for card in cards) == Counter(
        {account.account_id: config.cards.per_account for account in accounts}
    )
    assert set(field.name for field in fields(DebitCard)).isdisjoint(
        {"pan", "card_number", "cvv", "pin", "password", "magnetic_track"}
    )


def test_cards_obey_type_status_rate_dates_currency_and_decimal(domain: tuple) -> None:
    config, accounts, cards, _ = domain
    account_by_id = {account.account_id: account for account in accounts}
    expected_blocked = int(
        (Decimal(len(cards)) * config.cards.initially_blocked_rate).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )

    assert all(card.card_type is CardType.DEBIT for card in cards)
    assert sum(card.status is CardStatus.BLOCKED for card in cards) == expected_blocked
    assert all(
        card.currency == account_by_id[card.account_id].currency for card in cards
    )
    assert all(card.issued_date <= config.reference_date for card in cards)
    assert all(card.expiration_date > card.issued_date for card in cards)
    assert all(isinstance(card.daily_purchase_limit, Decimal) for card in cards)
    assert all(card.daily_purchase_limit.as_tuple().exponent == -2 for card in cards)
    assert all(
        config.cards.daily_purchase_limit.min
        <= card.daily_purchase_limit
        <= config.cards.daily_purchase_limit.max
        for card in cards
    )


def test_merchants_are_synthetic_coherent_and_bounded(domain: tuple) -> None:
    config, _, _, merchants = domain
    identifiers = [merchant.merchant_id for merchant in merchants]

    assert len(merchants) == config.merchants.count
    assert len(identifiers) == len(set(identifiers))
    assert all(value.startswith("SYN-MER-") for value in identifiers)
    assert all("Sintético" in merchant.synthetic_name for merchant in merchants)
    assert all(
        merchant.category_code == MERCHANT_CATEGORY_CODES[merchant.category]
        for merchant in merchants
    )
    assert all(code.startswith("SYN-MCC-") for code in MERCHANT_CATEGORY_CODES.values())
    assert all(merchant.created_date <= config.reference_date for merchant in merchants)
    assert "cnpj" not in {field.name.lower() for field in fields(Merchant)}


def test_new_entities_match_pyarrow_schemas(domain: tuple) -> None:
    _, _, cards, merchants = domain
    card_table = cards_to_table(cards)
    merchant_table = merchants_to_table(merchants)

    assert card_table.schema == CARD_SCHEMA
    assert merchant_table.schema == MERCHANT_SCHEMA
    assert card_table.column_names == CARD_SCHEMA.names
    assert merchant_table.column_names == MERCHANT_SCHEMA.names
    assert all(
        isinstance(value, Decimal)
        for value in card_table["daily_purchase_limit"].to_pylist()
    )
    assert CARD_SCHEMA == pa.schema(CARD_SCHEMA)


def test_validation_rejects_orphan_card_and_incoherent_category(domain: tuple) -> None:
    config, accounts, cards, merchants = domain
    with pytest.raises(ExtendedDomainValidationError, match="conta inexistente"):
        validate_cards_and_merchants(
            config,
            accounts,
            [replace(cards[0], account_id="SYN-ACC-MISSING"), *cards[1:]],
            merchants,
        )
    with pytest.raises(ExtendedDomainValidationError, match="categoria incoerente"):
        validate_cards_and_merchants(
            config,
            accounts,
            cards,
            [replace(merchants[0], category_code="SYN-MCC-WRONG"), *merchants[1:]],
        )
