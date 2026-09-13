from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from banking_data_generator.accounting import (
    calculate_all_account_balances,
    generate_opening_entries,
)
from banking_data_generator.config import load_config
from banking_data_generator.domain.enums import (
    CardStatus,
    MerchantStatus,
    TransactionStatus,
    TransactionType,
)
from banking_data_generator.generation import (
    calculate_reversal_target,
    generate_accounts,
    generate_card_purchases,
    generate_cards,
    generate_customers,
    generate_merchants,
    generate_purchase_reversals,
)
from banking_data_generator.validation import (
    ReversalValidationError,
    calculate_net_daily_consumption,
    reconcile_reversal_balances,
    validate_purchase_reversals,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


def _generated(rate: str = "0.50"):
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        customers=replace(config.customers, count=6),
        merchants=replace(config.merchants, count=5),
        cards=replace(config.cards, initially_blocked_rate=Decimal("0")),
        transactions=replace(
            config.transactions,
            count=20,
            declined_rate_overall=Decimal("0"),
            reversal_rate_of_approved=Decimal(rate),
        ),
    )
    accounts = generate_accounts(generate_customers(config), config)
    cards = [
        replace(item, status=CardStatus.ACTIVE)
        for item in generate_cards(accounts, config)
    ]
    merchants = [
        replace(item, status=MerchantStatus.ACTIVE)
        for item in generate_merchants(config)
    ]
    purchases = generate_card_purchases(accounts, cards, merchants, config)
    reversals = generate_purchase_reversals(purchases.transactions, config)
    return config, accounts, cards, purchases, reversals


def test_target_uses_half_up_and_zero_without_approvals() -> None:
    assert calculate_reversal_target(5, Decimal("0.50")) == 3
    assert calculate_reversal_target(0, Decimal("1.00")) == 0
    config, _, _, purchases, _ = _generated("1.00")
    declined = [
        replace(item, status=TransactionStatus.DECLINED)
        for item in purchases.transactions
    ]
    assert generate_purchase_reversals(declined, config).reversals == []


def test_selection_is_deterministic_unique_and_preserves_purchases() -> None:
    config, _, _, purchases, result = _generated()
    snapshot = list(purchases.transactions)
    assert result == generate_purchase_reversals(purchases.transactions, config)
    assert (
        result.reversals
        != generate_purchase_reversals(
            purchases.transactions, replace(config, seed=config.seed + 1)
        ).reversals
    )
    assert purchases.transactions == snapshot
    assert len(result.reversals) == result.target_reversals
    originals = [item.original_transaction_id for item in result.reversals]
    approved = {
        item.transaction_id
        for item in purchases.transactions
        if item.status is TransactionStatus.APPROVED
    }
    assert len(originals) == len(set(originals))
    assert set(originals) <= approved


def test_reversal_matches_original_timestamp_and_credit() -> None:
    config, _, _, purchases, result = _generated("1.00")
    originals = {item.transaction_id: item for item in purchases.transactions}
    entries = {item.reference_id: item for item in result.ledger_entries}
    for reversal in result.reversals:
        original = originals[reversal.original_transaction_id]
        assert reversal.transaction_id.startswith("SYN-TXN-")
        assert reversal.transaction_type is TransactionType.CARD_PURCHASE_REVERSAL
        assert reversal.status is TransactionStatus.COMPLETED
        assert reversal.decline_reason is None
        assert reversal.amount == original.amount
        assert reversal.currency == original.currency
        assert reversal.effective_at > original.effective_at
        assert reversal.effective_at.tzinfo is not None
        assert entries[reversal.transaction_id].amount == original.amount
    validate_purchase_reversals(
        config, purchases.transactions, result.reversals, result.ledger_entries
    )


def test_reversals_restore_balance_and_daily_consumption() -> None:
    _, accounts, cards, purchases, result = _generated("1.00")
    ledger = [
        *generate_opening_entries(accounts),
        *purchases.ledger_entries,
        *result.ledger_entries,
    ]
    balances = calculate_all_account_balances(accounts, ledger)
    reconcile_reversal_balances(
        accounts, purchases.transactions, result.reversals, balances
    )
    consumption = calculate_net_daily_consumption(
        cards, purchases.transactions, result.reversals
    )
    assert all(value >= 0 for value in consumption.values())


def test_validation_rejects_missing_declined_duplicate_and_chained_original() -> None:
    config, _, _, purchases, result = _generated("1.00")
    reversal = result.reversals[0]
    entry = result.ledger_entries[0]
    with pytest.raises(ReversalValidationError, match="original inexistente"):
        validate_purchase_reversals(
            config,
            purchases.transactions,
            [replace(reversal, original_transaction_id="SYN-TXN-MISSING")],
            [entry],
        )
    original_id = reversal.original_transaction_id
    declined = [
        replace(item, status=TransactionStatus.DECLINED)
        if item.transaction_id == original_id
        else item
        for item in purchases.transactions
    ]
    with pytest.raises(ReversalValidationError, match="original recusado"):
        validate_purchase_reversals(config, declined, [reversal], [entry])
    with pytest.raises(ReversalValidationError, match="mais de um estorno"):
        validate_purchase_reversals(
            config,
            purchases.transactions,
            [reversal, replace(reversal, transaction_id="SYN-TXN-REV-DUP")],
            [entry],
        )
    chained = [
        replace(item, transaction_type=TransactionType.CARD_PURCHASE_REVERSAL)
        if item.transaction_id == original_id
        else item
        for item in purchases.transactions
    ]
    with pytest.raises(ReversalValidationError, match="cadeia"):
        validate_purchase_reversals(config, chained, [reversal], [entry])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount", Decimal("1.00")),
        ("currency", "USD"),
        ("account_id", "SYN-ACC-WRONG"),
        ("card_id", "SYN-CRD-WRONG"),
        ("merchant_id", "SYN-MER-WRONG"),
    ],
)
def test_validation_rejects_divergent_attributes(field: str, value: object) -> None:
    config, _, _, purchases, result = _generated("1.00")
    reversal = replace(result.reversals[0], **{field: value})
    with pytest.raises(ReversalValidationError, match="divergente"):
        validate_purchase_reversals(
            config, purchases.transactions, [reversal], [result.ledger_entries[0]]
        )


def test_validation_rejects_non_posterior_timestamp() -> None:
    config, _, _, purchases, result = _generated("1.00")
    original = next(
        item
        for item in purchases.transactions
        if item.transaction_id == result.reversals[0].original_transaction_id
    )
    reversal = replace(
        result.reversals[0],
        effective_at=original.effective_at,
        event_at=original.effective_at + timedelta(seconds=1),
        ingested_at=original.effective_at + timedelta(seconds=1),
    )
    with pytest.raises(ReversalValidationError, match="effective_at"):
        validate_purchase_reversals(
            config, purchases.transactions, [reversal], [result.ledger_entries[0]]
        )


def test_validation_rejects_missing_credit() -> None:
    config, _, _, purchases, result = _generated("1.00")
    with pytest.raises(ReversalValidationError, match="crédito ausente"):
        validate_purchase_reversals(
            config, purchases.transactions, [result.reversals[0]], []
        )
