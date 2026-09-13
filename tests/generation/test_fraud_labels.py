from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pyarrow.csv as pa_csv
import pytest

from banking_data_generator.config import load_config
from banking_data_generator.domain.enums import CardStatus, MerchantStatus, RiskPattern
from banking_data_generator.domain.schemas import (
    TRANSACTION_LABEL_SCHEMA,
    TRANSACTION_SCHEMA,
)
from banking_data_generator.export import transaction_labels_to_table
from banking_data_generator.generation import (
    calculate_fraud_target,
    generate_accounts,
    generate_card_purchases,
    generate_cards,
    generate_customers,
    generate_merchants,
    generate_purchase_reversals,
)
from banking_data_generator.validation import (
    FraudLabelValidationError,
    validate_card_purchases,
    validate_transaction_labels,
)
from banking_data_generator.version import TRANSACTION_LABEL_VERSION

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


def _fraud_domain(count: int = 30, rate: Decimal = Decimal("0.50")):
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        customers=replace(config.customers, count=6),
        merchants=replace(config.merchants, count=5),
        cards=replace(config.cards, initially_blocked_rate=Decimal("0")),
        transactions=replace(
            config.transactions,
            count=count,
            fraud_rate_overall=rate,
            declined_rate_overall=Decimal("0.30"),
        ),
    )
    accounts = generate_accounts(generate_customers(config), config)
    cards = [
        replace(card, status=CardStatus.ACTIVE)
        for card in generate_cards(accounts, config)
    ]
    merchants = [
        replace(merchant, status=MerchantStatus.ACTIVE)
        for merchant in generate_merchants(config)
    ]
    return config, accounts, cards, merchants


def test_target_uses_round_half_up() -> None:
    assert calculate_fraud_target(5, Decimal("0.10")) == 1
    assert calculate_fraud_target(5, Decimal("0.50")) == 3
    assert calculate_fraud_target(0, Decimal("1.00")) == 0


def test_labels_are_deterministic_complete_and_seed_isolated() -> None:
    config, accounts, cards, merchants = _fraud_domain()
    first = generate_card_purchases(accounts, cards, merchants, config)
    second = generate_card_purchases(accounts, cards, merchants, config)
    assert first == second
    assert len(first.labels) == len(first.transactions) == 30
    assert len({label.transaction_id for label in first.labels}) == 30
    assert {label.transaction_id for label in first.labels} == {
        item.transaction_id for item in first.transactions
    }
    assert sum(label.is_synthetic_fraud for label in first.labels) == 15
    assert first.target_fraud_count == 15
    unrelated = replace(config, transfers=replace(config.transfers, count=999))
    assert first == generate_card_purchases(accounts, cards, merchants, unrelated)
    changed = replace(config, seed=config.seed + 1)
    assert first != generate_card_purchases(accounts, cards, merchants, changed)


def test_three_patterns_are_verifiable_and_financial_rules_still_apply() -> None:
    config, accounts, cards, merchants = _fraud_domain()
    result = generate_card_purchases(accounts, cards, merchants, config)
    validate_transaction_labels(config, accounts, result.transactions, result.labels)
    validate_card_purchases(
        config, accounts, cards, merchants, result.transactions, result.ledger_entries
    )
    fraudulent = [label for label in result.labels if label.is_synthetic_fraud]
    assert {label.risk_pattern for label in fraudulent} == set(RiskPattern)
    assert all(label.risk_score >= Decimal("85.00") for label in fraudulent)
    normal = [label for label in result.labels if not label.is_synthetic_fraud]
    assert all(label.risk_pattern is None for label in normal)
    assert all(label.risk_score == Decimal("0.00") for label in normal)
    assert all(
        label.label_version == TRANSACTION_LABEL_VERSION for label in result.labels
    )
    approved_ids = {entry.reference_id for entry in result.ledger_entries}
    assert approved_ids == {
        item.transaction_id
        for item in result.transactions
        if item.status.value == "approved"
    }


def test_fraud_classification_is_independent_of_status() -> None:
    config, accounts, cards, merchants = _fraud_domain(rate=Decimal("1.00"))
    active = generate_card_purchases(accounts, cards, merchants, config)
    blocked_cards = [replace(card, status=CardStatus.BLOCKED) for card in cards]
    blocked = generate_card_purchases(accounts, blocked_cards, merchants, config)
    assert all(label.is_synthetic_fraud for label in active.labels)
    assert all(label.is_synthetic_fraud for label in blocked.labels)
    assert any(item.status.value == "approved" for item in active.transactions)
    assert all(item.status.value == "declined" for item in blocked.transactions)
    assert not blocked.ledger_entries


def test_reversals_have_no_labels_and_extra_label_is_rejected() -> None:
    config, accounts, cards, merchants = _fraud_domain()
    purchases = generate_card_purchases(accounts, cards, merchants, config)
    reversals = generate_purchase_reversals(purchases.transactions, config)
    events = [*purchases.transactions, *reversals.reversals]
    validate_transaction_labels(config, accounts, events, purchases.labels)
    if reversals.reversals:
        invalid = replace(
            purchases.labels[0],
            transaction_id=reversals.reversals[0].transaction_id,
        )
        with pytest.raises(FraudLabelValidationError, match="exatamente um rótulo"):
            validate_transaction_labels(
                config, accounts, events, [*purchases.labels, invalid]
            )


def test_label_schema_round_trip_and_no_leak_in_transaction_schema(
    tmp_path: Path,
) -> None:
    config, accounts, cards, merchants = _fraud_domain()
    result = generate_card_purchases(accounts, cards, merchants, config)
    table = transaction_labels_to_table(result.labels)
    assert table.schema == TRANSACTION_LABEL_SCHEMA
    assert "is_synthetic_fraud" not in TRANSACTION_SCHEMA.names
    assert "risk_pattern" not in TRANSACTION_SCHEMA.names
    path = tmp_path / "transaction_labels.csv"
    pa_csv.write_csv(table, path)
    restored = pa_csv.read_csv(path)
    assert restored.num_rows == len(result.labels)
    assert set(restored.column("transaction_id").to_pylist()) == {
        item.transaction_id for item in result.transactions
    }
