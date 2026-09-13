"""Validação do ground truth sintético de fraude em compras."""

from collections import Counter
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.domain.enums import RiskPattern, TransactionType
from banking_data_generator.domain.models import Account, Transaction, TransactionLabel
from banking_data_generator.generation.transactions import (
    calculate_fraud_target,
    fraud_pattern_plan,
)
from banking_data_generator.version import TRANSACTION_LABEL_VERSION

_MIN_SCORE = Decimal("0.00")
_MAX_SCORE = Decimal("100.00")
_RAPID_WINDOW = timedelta(minutes=5)


class FraudLabelValidationError(ValueError):
    """Indica um ground truth incompleto ou incoerente."""


def validate_transaction_labels(
    config: BankingDataGeneratorConfig,
    accounts: Sequence[Account],
    transaction_events: Sequence[Transaction],
    labels: Sequence[TransactionLabel],
) -> None:
    """Valide cobertura, cota e evidências dos padrões sintéticos."""
    purchases = [
        item
        for item in transaction_events
        if item.transaction_type is TransactionType.CARD_PURCHASE
    ]
    purchase_by_id = {item.transaction_id: item for item in purchases}
    label_ids = [item.transaction_id for item in labels]
    if len(label_ids) != len(set(label_ids)):
        _fail("transaction_id duplicado")
    if set(label_ids) != set(purchase_by_id):
        _fail("deve existir exatamente um rótulo para cada tentativa original")
    target = calculate_fraud_target(
        len(purchases), config.transactions.fraud_rate_overall
    )
    fraud_labels = [item for item in labels if item.is_synthetic_fraud]
    if len(fraud_labels) != target:
        _fail(f"quantidade de fraude divergente; esperada {target}")
    newest_opened_date = max(
        (item.opened_date for item in accounts), default=config.reference_date
    )
    account_by_id = {item.account_id: item for item in accounts}
    purchases_by_card: dict[str, list[Transaction]] = {}
    for purchase in purchases:
        purchases_by_card.setdefault(purchase.card_id, []).append(purchase)
    pattern_counts: Counter[RiskPattern] = Counter()
    for label in labels:
        purchase = purchase_by_id[label.transaction_id]
        if label.label_version != TRANSACTION_LABEL_VERSION:
            _fail(f"label_version inválida em '{label.transaction_id}'")
        if (
            not isinstance(label.risk_score, Decimal)
            or label.risk_score.as_tuple().exponent != -2
            or not _MIN_SCORE <= label.risk_score <= _MAX_SCORE
        ):
            _fail(f"risk_score inválido em '{label.transaction_id}'")
        if label.is_synthetic_fraud != (label.risk_pattern is not None):
            _fail(f"booleano e padrão divergentes em '{label.transaction_id}'")
        if label.risk_pattern is None:
            if label.risk_score != _MIN_SCORE:
                _fail(
                    "comportamento normal com score não zero em "
                    f"'{label.transaction_id}'"
                )
            continue
        if label.risk_pattern not in set(RiskPattern):
            _fail(f"padrão inválido em '{label.transaction_id}'")
        pattern_counts[label.risk_pattern] += 1
        if label.risk_pattern is RiskPattern.HIGH_AMOUNT:
            if purchase.amount != config.transactions.purchase_amount.max:
                _fail(f"high_amount sem valor máximo em '{label.transaction_id}'")
        elif label.risk_pattern is RiskPattern.RAPID_VELOCITY:
            peers = purchases_by_card[purchase.card_id]
            if not any(
                peer.transaction_id != purchase.transaction_id
                and abs(peer.effective_at - purchase.effective_at) <= _RAPID_WINDOW
                for peer in peers
            ):
                _fail(f"rapid_velocity sem sequência em '{label.transaction_id}'")
        else:
            account = account_by_id[purchase.account_id]
            if account.opened_date != newest_opened_date:
                _fail(
                    "new_account_burst fora da conta mais nova em "
                    f"'{label.transaction_id}'"
                )
            if purchase.effective_at.date() != config.reference_date:
                _fail(
                    "new_account_burst fora da data de referência em "
                    f"'{label.transaction_id}'"
                )
    expected_patterns = fraud_pattern_plan(target)
    if pattern_counts != Counter(expected_patterns):
        _fail("distribuição entre padrões divergente")


def _fail(message: str) -> None:
    raise FraudLabelValidationError(f"Rótulos de fraude inválidos: {message}.")
