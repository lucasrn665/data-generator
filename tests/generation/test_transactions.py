from dataclasses import replace
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
    DeclineReason,
    EntryDirection,
    MerchantStatus,
    TransactionStatus,
)
from banking_data_generator.domain.schemas import TRANSACTION_SCHEMA
from banking_data_generator.export import transactions_to_table
from banking_data_generator.generation import (
    generate_accounts,
    generate_card_purchases,
    generate_cards,
    generate_customers,
    generate_merchants,
)
from banking_data_generator.validation import (
    reconcile_purchase_balances,
    validate_card_purchases,
)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


def _domain(count: int = 20):
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        customers=replace(config.customers, count=4),
        merchants=replace(config.merchants, count=4),
        cards=replace(config.cards, initially_blocked_rate=Decimal("0")),
        transactions=replace(config.transactions, count=count),
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


def test_purchases_are_deterministic_isolated_and_structurally_valid() -> None:
    config, accounts, cards, merchants = _domain()
    first = generate_card_purchases(accounts, cards, merchants, config)
    assert first == generate_card_purchases(accounts, cards, merchants, config)
    assert first != generate_card_purchases(
        accounts, cards, merchants, replace(config, seed=config.seed + 1)
    )
    assert len(first.transactions) == config.transactions.count
    assert len({item.transaction_id for item in first.transactions}) == len(
        first.transactions
    )
    assert all(
        item.transaction_id.startswith("SYN-TXN-") for item in first.transactions
    )
    assert all(item.original_transaction_id is None for item in first.transactions)
    assert all(item.effective_at.tzinfo is not None for item in first.transactions)
    validate_card_purchases(
        config, accounts, cards, merchants, first.transactions, first.ledger_entries
    )


def test_approved_purchase_has_one_debit_and_decline_has_none() -> None:
    config, accounts, cards, merchants = _domain(30)
    result = generate_card_purchases(accounts, cards, merchants, config)
    entries = {entry.reference_id: entry for entry in result.ledger_entries}
    for transaction in result.transactions:
        if transaction.status is TransactionStatus.APPROVED:
            assert transaction.decline_reason is None
            assert entries[transaction.transaction_id].direction is EntryDirection.DEBIT
            assert entries[transaction.transaction_id].amount == transaction.amount
        else:
            assert transaction.decline_reason is not None
            assert transaction.transaction_id not in entries


@pytest.mark.parametrize(
    ("card_status", "merchant_status", "reason"),
    [
        (CardStatus.BLOCKED, MerchantStatus.ACTIVE, DeclineReason.CARD_BLOCKED),
        (CardStatus.ACTIVE, MerchantStatus.INACTIVE, DeclineReason.MERCHANT_INACTIVE),
    ],
)
def test_state_driven_declines(card_status, merchant_status, reason) -> None:
    config, accounts, cards, merchants = _domain(5)
    config = replace(
        config,
        transactions=replace(config.transactions, declined_rate_overall=Decimal("0")),
    )
    cards = [replace(card, status=card_status) for card in cards]
    merchants = [replace(merchant, status=merchant_status) for merchant in merchants]
    result = generate_card_purchases(accounts, cards, merchants, config)
    assert {item.decline_reason for item in result.transactions} == {reason}
    assert result.ledger_entries == []


def test_insufficient_funds_and_daily_limit_are_enforced() -> None:
    config, accounts, cards, merchants = _domain(2)
    config = replace(
        config,
        transactions=replace(
            config.transactions,
            purchase_amount=replace(
                config.transactions.purchase_amount,
                min=Decimal("60.00"),
                max=Decimal("60.00"),
            ),
            history_days=1,
            declined_rate_overall=Decimal("0"),
        ),
    )
    account = replace(accounts[0], opening_balance=Decimal("100.00"))
    card = replace(
        cards[0],
        account_id=account.account_id,
        daily_purchase_limit=Decimal("100.00"),
    )
    result = generate_card_purchases([account], [card], merchants, config)
    assert [item.status for item in result.transactions] == [
        TransactionStatus.APPROVED,
        TransactionStatus.DECLINED,
    ]
    assert result.transactions[1].decline_reason is DeclineReason.INSUFFICIENT_FUNDS

    rich = replace(account, opening_balance=Decimal("1000.00"))
    result = generate_card_purchases([rich], [card], merchants, config)
    assert result.transactions[1].decline_reason is DeclineReason.DAILY_LIMIT_EXCEEDED


def test_synthetic_decline_target_and_schema() -> None:
    config, accounts, cards, merchants = _domain(7)
    config = replace(
        config,
        transactions=replace(config.transactions, declined_rate_overall=Decimal("1")),
    )
    result = generate_card_purchases(accounts, cards, merchants, config)
    assert result.target_declines == 7
    assert result.planned_declines == 7
    assert result.additional_declines == 0
    assert {item.decline_reason for item in result.transactions} == {
        DeclineReason.SYNTHETIC_RISK_RULE
    }
    table = transactions_to_table(result.transactions)
    assert table.schema == TRANSACTION_SCHEMA
    assert table.num_rows == 7


def test_final_balance_is_derived_and_reconciled() -> None:
    config, accounts, cards, merchants = _domain(20)
    result = generate_card_purchases(accounts, cards, merchants, config)
    opening = generate_opening_entries(accounts)
    balances = calculate_all_account_balances(
        accounts, [*opening, *result.ledger_entries]
    )
    assert all(value >= Decimal("0.00") for value in balances.values())
    reconcile_purchase_balances(accounts, result.transactions, balances)
