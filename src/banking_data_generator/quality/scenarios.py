"""Mutações determinísticas aplicadas somente às tabelas de publicação."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import pyarrow as pa

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.generation.context import GenerationContext
from banking_data_generator.version import QUALITY_SCENARIO_VERSION

_PRIMARY_KEYS = {
    "customers": "customer_id",
    "addresses": "address_id",
    "accounts": "account_id",
    "cards": "card_id",
    "merchants": "merchant_id",
    "transactions": "transaction_id",
}
_FILENAMES = {entity: f"{entity}.csv" for entity in _PRIMARY_KEYS}
_VIOLATION_TYPES = {
    "valid": "none",
    "duplicate_exact": "duplicate_primary_key_exact",
    "duplicate_conflicting": "duplicate_primary_key_conflicting",
    "required_null": "required_field_null",
    "orphan_foreign_key": "orphan_foreign_key",
}
_ALLOWED_FIELDS = {
    "duplicate_conflicting": {
        "customers": {"synthetic_name"},
        "addresses": {"street", "neighborhood", "city", "state", "country"},
        "merchants": {"synthetic_name", "city", "state", "country"},
    },
    "required_null": {
        "customers": {"synthetic_name", "synthetic_email"},
        "addresses": {"street", "neighborhood", "city", "state", "country"},
        "merchants": {"synthetic_name", "city", "state", "country"},
    },
    "orphan_foreign_key": {
        "addresses": {"customer_id"},
        "accounts": {"customer_id"},
        "cards": {"account_id"},
        "transactions": {"merchant_id"},
    },
}


class QualityScenarioError(ValueError):
    """Indica cenário impossível ou mutação além do contrato autorizado."""


@dataclass(frozen=True, slots=True)
class QualityScenarioResult:
    tables: dict[str, pa.Table]
    scenario: str
    target_entity: str
    target_field: str | None
    configured_rate: Decimal
    calculated_count: int
    affected_count: int
    expected_violation_count: int
    expected_violation_type: str
    original_count: int
    published_count: int
    selected_record_count: int
    additional_row_count: int
    duplicate_key_count: int
    canonical_validation_passed: bool
    version: str


def calculate_affected_count(record_count: int, rate: Decimal) -> int:
    """Calcule a quantidade sem impor mínimo implícito."""
    return int(
        (Decimal(record_count) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def apply_quality_scenario(
    tables: Mapping[str, pa.Table],
    config: BankingDataGeneratorConfig,
) -> QualityScenarioResult:
    """Crie tabelas novas e confirme que somente a violação esperada surgiu."""
    copied = dict(tables)
    scenario = config.quality.scenario
    entity = config.quality.entity
    filename = _FILENAMES[entity]
    canonical = tables[filename]
    original_count = canonical.num_rows
    calculated = (
        0
        if scenario == "valid"
        else calculate_affected_count(original_count, config.quality.rate)
    )
    selected = _select_indices(original_count, calculated, config, scenario)
    field = (
        config.quality.field if scenario not in {"valid", "duplicate_exact"} else None
    )
    if scenario in _ALLOWED_FIELDS and field not in _ALLOWED_FIELDS[scenario].get(
        entity, set()
    ):
        raise QualityScenarioError(
            "Combinação de entidade e campo não permitida para "
            f"'{scenario}': '{entity}.{field}'."
        )
    if scenario == "valid":
        published = canonical
    else:
        published = _mutate_table(canonical, scenario, field, selected)
        copied[filename] = published
    result = QualityScenarioResult(
        tables=copied,
        scenario=scenario,
        target_entity=entity,
        target_field=field,
        configured_rate=config.quality.rate,
        calculated_count=calculated,
        affected_count=len(selected),
        expected_violation_count=len(selected),
        expected_violation_type=_VIOLATION_TYPES[scenario],
        original_count=original_count,
        published_count=published.num_rows,
        selected_record_count=len(selected),
        additional_row_count=(len(selected) if scenario.startswith("duplicate") else 0),
        duplicate_key_count=(len(selected) if scenario.startswith("duplicate") else 0),
        canonical_validation_passed=True,
        version=QUALITY_SCENARIO_VERSION,
    )
    _validate_scenario_result(tables, result)
    return result


def _select_indices(
    count: int,
    affected: int,
    config: BankingDataGeneratorConfig,
    scenario: str,
) -> list[int]:
    context = GenerationContext.create(config.seed, f"quality_scenario:{scenario}")
    return sorted(context.random.sample(range(count), affected))


def _mutate_table(
    table: pa.Table,
    scenario: str,
    field: str | None,
    selected: list[int],
) -> pa.Table:
    records = table.to_pylist()
    if scenario == "duplicate_exact":
        records.extend(dict(records[index]) for index in selected)
    elif scenario == "duplicate_conflicting":
        assert field is not None
        for index in selected:
            duplicate = dict(records[index])
            duplicate[field] = f"{duplicate[field]} [CONFLITO-SINTETICO]"
            records.append(duplicate)
    elif scenario == "required_null":
        assert field is not None
        for index in selected:
            records[index] = {**records[index], field: None}
    elif scenario == "orphan_foreign_key":
        assert field is not None
        for sequence, index in enumerate(selected, start=1):
            records[index] = {
                **records[index],
                field: f"SYN-MISSING-{sequence:012d}",
            }
    else:
        raise QualityScenarioError(f"Cenário de qualidade desconhecido: '{scenario}'.")
    return pa.Table.from_pylist(records, schema=table.schema)


def _validate_scenario_result(
    canonical_tables: Mapping[str, pa.Table],
    result: QualityScenarioResult,
) -> None:
    target_filename = _FILENAMES[result.target_entity]
    for filename, canonical in canonical_tables.items():
        published = result.tables[filename]
        if filename != target_filename and not published.equals(canonical):
            _fail(f"arquivo não alvo alterado: '{filename}'")
    canonical = canonical_tables[target_filename]
    published = result.tables[target_filename]
    if result.scenario == "valid":
        if not published.equals(canonical):
            _fail("o cenário válido foi alterado")
        return
    original = canonical.to_pylist()
    mutated = published.to_pylist()
    primary_key = _PRIMARY_KEYS[result.target_entity]
    if result.scenario.startswith("duplicate"):
        if mutated[: len(original)] != original:
            _fail("registros canônicos foram modificados por duplicação")
        duplicate_counts = Counter(row[primary_key] for row in mutated)
        duplicate_keys = sum(count > 1 for count in duplicate_counts.values())
        if duplicate_keys != result.duplicate_key_count:
            _fail("quantidade de chaves duplicadas divergente")
        for extra in mutated[len(original) :]:
            base = next(
                row for row in original if row[primary_key] == extra[primary_key]
            )
            differing = {name for name in base if base[name] != extra[name]}
            expected = (
                set() if result.scenario == "duplicate_exact" else {result.target_field}
            )
            if differing != expected:
                _fail("linha duplicada possui diferenças inesperadas")
    else:
        changed = []
        for before, after in zip(original, mutated, strict=True):
            differences = {name for name in before if before[name] != after[name]}
            if differences:
                changed.append((before, after, differences))
        if len(changed) != result.affected_count:
            _fail("quantidade de registros alterados divergente")
        if any(item[2] != {result.target_field} for item in changed):
            _fail("campo não autorizado foi alterado")
        if result.scenario == "required_null" and any(
            after[result.target_field] is not None for _, after, _ in changed
        ):
            _fail("campo obrigatório não foi anulado")
        if result.scenario == "orphan_foreign_key" and any(
            not after[result.target_field].startswith("SYN-MISSING-")
            for _, after, _ in changed
        ):
            _fail("chave órfã não possui prefixo sintético")


def _fail(message: str) -> None:
    raise QualityScenarioError(f"Cenário de qualidade inválido: {message}.")
