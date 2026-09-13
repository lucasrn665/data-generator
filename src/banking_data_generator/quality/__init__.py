"""Cenários controlados derivados de tabelas canônicas válidas."""

from banking_data_generator.quality.scenarios import (
    QualityScenarioError,
    QualityScenarioResult,
    apply_quality_scenario,
    calculate_affected_count,
)

__all__ = [
    "QualityScenarioError",
    "QualityScenarioResult",
    "apply_quality_scenario",
    "calculate_affected_count",
]
