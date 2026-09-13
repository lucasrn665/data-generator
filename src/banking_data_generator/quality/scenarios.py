"""Mutações determinísticas aplicadas somente às tabelas de publicação."""

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
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
    "late_event": "late_event",
    "schema_additive_column": "schema_additive_column",
    "schema_missing_column": "schema_missing_column",
    "schema_renamed_column": "schema_renamed_column",
    "schema_incompatible_value": "schema_incompatible_value",
    "schema_unknown_enum": "schema_unknown_enum",
}
_SCHEMA_SCENARIOS = {
    "schema_additive_column",
    "schema_missing_column",
    "schema_renamed_column",
    "schema_incompatible_value",
    "schema_unknown_enum",
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
    late_event_target_count: int = 0
    late_event_observed_count: int = 0
    minimum_delay_seconds: int = 0
    maximum_delay_seconds: int = 0
    late_threshold_seconds: int = 0
    observed_columns: tuple[str, ...] = ()
    added_column: str | None = None
    missing_column: str | None = None
    renamed_from: str | None = None
    renamed_to: str | None = None
    expected_columns: tuple[str, ...] = ()


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
    entity = (
        "transactions"
        if scenario == "late_event" or scenario in _SCHEMA_SCENARIOS
        else config.quality.entity
    )
    filename = _FILENAMES[entity]
    canonical = tables[filename]
    _validate_canonical_arrivals(tables["transactions.csv"], config)
    original_count = canonical.num_rows
    calculated = (
        0
        if scenario == "valid"
        else calculate_affected_count(
            len(tables["transactions.csv"]), config.transactions.late_event_rate_overall
        )
        if scenario == "late_event"
        else calculate_affected_count(original_count, config.quality.rate)
    )
    selected = (
        list(range(original_count))
        if scenario == "schema_additive_column"
        else _select_indices(original_count, calculated, config, scenario)
    )
    field = (
        "ingested_at"
        if scenario == "late_event"
        else config.quality.field
        if scenario not in {"valid", "duplicate_exact"}
        else None
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
    elif scenario == "late_event":
        published = _apply_late_events(canonical, selected, config)
        copied[filename] = published
    elif scenario in _SCHEMA_SCENARIOS:
        published = _mutate_schema_table(canonical, scenario, selected)
        copied[filename] = published
    else:
        published = _mutate_table(canonical, scenario, field, selected)
        copied[filename] = published
    result = QualityScenarioResult(
        tables=copied,
        scenario=scenario,
        target_entity=entity,
        target_field=field,
        configured_rate=(
            config.transactions.late_event_rate_overall
            if scenario == "late_event"
            else config.quality.rate
        ),
        calculated_count=calculated,
        affected_count=len(selected),
        expected_violation_count=(
            0 if scenario == "schema_additive_column" else len(selected)
        ),
        expected_violation_type=_VIOLATION_TYPES[scenario],
        original_count=original_count,
        published_count=published.num_rows,
        selected_record_count=len(selected),
        additional_row_count=(len(selected) if scenario.startswith("duplicate") else 0),
        duplicate_key_count=(len(selected) if scenario.startswith("duplicate") else 0),
        canonical_validation_passed=True,
        version=QUALITY_SCENARIO_VERSION,
        late_event_target_count=(calculated if scenario == "late_event" else 0),
        late_event_observed_count=(calculated if scenario == "late_event" else 0),
        minimum_delay_seconds=_delay_extreme(copied["transactions.csv"], min),
        maximum_delay_seconds=_delay_extreme(copied["transactions.csv"], max),
        late_threshold_seconds=config.transactions.ingestion_delay.late_threshold_seconds,
        observed_columns=tuple(field.name for field in published.schema),
        expected_columns=tuple(field.name for field in canonical.schema),
        added_column="source_channel" if scenario == "schema_additive_column" else None,
        missing_column="merchant_id" if scenario == "schema_missing_column" else None,
        renamed_from="merchant_id" if scenario == "schema_renamed_column" else None,
        renamed_to="counterparty_id" if scenario == "schema_renamed_column" else None,
    )
    _validate_scenario_result(tables, result, config)
    return result


def _mutate_schema_table(
    table: pa.Table, scenario: str, selected: list[int]
) -> pa.Table:
    records = table.to_pylist()
    if scenario == "schema_additive_column":
        for row in records:
            row["source_channel"] = ("mobile", "web", "branch")[
                int(row["transaction_id"].split("-")[-1]) % 3
            ]
        return pa.Table.from_pylist(records)
    if scenario == "schema_missing_column":
        return pa.Table.from_pylist(
            [
                {key: value for key, value in row.items() if key != "merchant_id"}
                for row in records
            ]
        )
    if scenario == "schema_renamed_column":
        return pa.Table.from_pylist(
            [
                {
                    ("counterparty_id" if key == "merchant_id" else key): value
                    for key, value in row.items()
                }
                for row in records
            ]
        )
    if scenario == "schema_incompatible_value":
        for index in selected:
            records[index]["amount"] = f"INVALID_AMOUNT_{records[index]['amount']}"
        names = [field.name for field in table.schema]
        arrays = [
            pa.array([row[name] for row in records], type=field.type)
            if name != "amount"
            else pa.array([str(row[name]) for row in records])
            for name, field in zip(names, table.schema, strict=True)
        ]
        return pa.Table.from_arrays(arrays, names=names)
    if scenario == "schema_unknown_enum":
        for index in selected:
            records[index]["status"] = "pending_review"
        return pa.Table.from_pylist(records, schema=table.schema)
    raise QualityScenarioError(f"Cenário de qualidade desconhecido: '{scenario}'.")


def _apply_late_events(
    table: pa.Table, selected: list[int], config: BankingDataGeneratorConfig
) -> pa.Table:
    records = table.to_pylist()
    context = GenerationContext.create(
        config.seed, "quality_scenario:late_event:delays"
    )
    bounds = config.transactions.ingestion_delay
    for index in selected:
        records[index] = {
            **records[index],
            "ingested_at": records[index]["event_at"]
            + timedelta(
                seconds=context.random.randint(
                    bounds.late_min_seconds, bounds.late_max_seconds
                )
            ),
        }
    records.sort(key=lambda row: (row["ingested_at"], row["transaction_id"]))
    return pa.Table.from_pylist(records, schema=table.schema)


def _validate_canonical_arrivals(
    table: pa.Table, config: BankingDataGeneratorConfig
) -> None:
    maximum = config.transactions.ingestion_delay.operational_max_seconds
    for row in table.to_pylist():
        delay = int((row["ingested_at"] - row["event_at"]).total_seconds())
        if delay < 0:
            _fail("ingested_at anterior a event_at no conjunto canônico")
        if delay > maximum:
            _fail("conjunto canônico contém atraso fora do intervalo operacional")


def _delay_extreme(table: pa.Table, operation: Callable[[list[int]], int]) -> int:
    delays = [
        int((row["ingested_at"] - row["event_at"]).total_seconds())
        for row in table.to_pylist()
    ]
    return operation(delays) if delays else 0


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
    config: BankingDataGeneratorConfig,
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
    if result.scenario == "late_event":
        validate_late_event_scenario(canonical, published, result, config)
        return
    if result.scenario in _SCHEMA_SCENARIOS:
        _validate_schema_mutation(canonical, published, result)
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


def validate_late_event_scenario(
    canonical: pa.Table,
    published: pa.Table,
    result: QualityScenarioResult,
    config: BankingDataGeneratorConfig,
) -> None:
    before = {row["transaction_id"]: row for row in canonical.to_pylist()}
    rows = published.to_pylist()
    if rows != sorted(
        rows, key=lambda row: (row["ingested_at"], row["transaction_id"])
    ):
        _fail("eventos tardios não estão ordenados por chegada")
    changed = 0
    observed = 0
    for row in rows:
        original = before[row["transaction_id"]]
        differences = {key for key in row if row[key] != original[key]}
        if differences:
            if differences != {"ingested_at"}:
                _fail("evento tardio alterou coluna além de ingested_at")
            changed += 1
        if row["ingested_at"] < row["event_at"]:
            _fail("ingested_at anterior a event_at")
        delay = int((row["ingested_at"] - row["event_at"]).total_seconds())
        if delay > result.late_threshold_seconds:
            observed += 1
        if differences and delay <= result.late_threshold_seconds:
            _fail("evento selecionado não ultrapassa o limite tardio")
        if not differences and delay > result.late_threshold_seconds:
            _fail("evento não selecionado ultrapassa o limite tardio")
    if changed != result.late_event_target_count:
        _fail("quantidade observada de eventos tardios divergente")
    if observed != result.late_event_observed_count:
        _fail("classificação observada de eventos tardios divergente")
    expected_indices = _select_indices(
        canonical.num_rows, result.late_event_target_count, config, "late_event"
    )
    canonical_rows = canonical.to_pylist()
    expected_ids = {
        canonical_rows[index]["transaction_id"] for index in expected_indices
    }
    changed_ids = {
        row["transaction_id"]
        for row in rows
        if row["ingested_at"] != before[row["transaction_id"]]["ingested_at"]
    }
    if changed_ids != expected_ids:
        _fail("seleção de eventos tardios não é a determinística esperada")


def _validate_schema_mutation(
    canonical: pa.Table, published: pa.Table, result: QualityScenarioResult
) -> None:
    expected = [field.name for field in canonical.schema]
    observed = [field.name for field in published.schema]
    if result.scenario == "schema_additive_column":
        if observed != [*expected, "source_channel"]:
            _fail("colunas observadas não correspondem à adição declarada")
        if any(
            row["source_channel"] not in {"mobile", "web", "branch"}
            for row in published.to_pylist()
        ):
            _fail("source_channel contém valor não permitido")
        for before, after in zip(
            canonical.to_pylist(), published.to_pylist(), strict=True
        ):
            if any(before[name] != after[name] for name in expected):
                _fail("adição de coluna alterou valores canônicos")
        return
    if result.scenario == "schema_missing_column":
        if observed != [name for name in expected if name != "merchant_id"]:
            _fail("colunas observadas não correspondem à remoção declarada")
        for before, after in zip(
            canonical.to_pylist(), published.to_pylist(), strict=True
        ):
            if any(before[key] != after[key] for key in after):
                _fail("remoção de coluna alterou valores")
        return
    if result.scenario == "schema_renamed_column":
        if observed != [
            "counterparty_id" if name == "merchant_id" else name for name in expected
        ]:
            _fail("colunas observadas não correspondem à renomeação declarada")
        for before, after in zip(
            canonical.to_pylist(), published.to_pylist(), strict=True
        ):
            if before["merchant_id"] != after["counterparty_id"] or any(
                before[name] != after[name]
                for name in expected
                if name != "merchant_id"
            ):
                _fail("renomeação alterou valores")
        return
    if observed != expected:
        _fail("a mutação de valor alterou colunas inesperadamente")
    canonical_rows = canonical.to_pylist()
    published_rows = published.to_pylist()
    changed = [
        index
        for index, (before, after) in enumerate(
            zip(canonical_rows, published_rows, strict=True)
        )
        if any(before[key] != after[key] for key in before if key != "amount")
        or str(before["amount"]) != str(after["amount"])
    ]
    if result.scenario == "schema_incompatible_value":
        if len(changed) != result.calculated_count or any(
            not str(published_rows[index]["amount"]).startswith("INVALID_AMOUNT_")
            for index in changed
        ):
            _fail("quantidade ou conteúdo da incompatibilidade monetária divergente")
    elif result.scenario == "schema_unknown_enum":
        if len(changed) != result.calculated_count or any(
            {
                key: canonical_rows[index][key]
                for key in canonical_rows[index]
                if key != "status"
            }
            != {
                key: published_rows[index][key]
                for key in published_rows[index]
                if key != "status"
            }
            or published_rows[index]["status"] != "pending_review"
            for index in changed
        ):
            _fail("quantidade ou conteúdo do enum desconhecido divergente")
