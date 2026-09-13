"""Erros esperados das validações contábeis."""


class AccountingError(ValueError):
    """Base para violações conhecidas do subledger."""


class LedgerValidationError(AccountingError):
    """Indica uma invariável inválida em lançamentos."""


class BalanceReconciliationError(AccountingError):
    """Indica falha no cálculo ou na reconciliação de saldos."""
