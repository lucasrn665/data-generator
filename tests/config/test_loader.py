from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from banking_data_generator.config import ConfigError, load_config

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


@pytest.fixture
def valid_config() -> dict[str, object]:
    with DEFAULT_CONFIG.open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def write_config(tmp_path: Path, config: object) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def test_loads_default_config_with_typed_values() -> None:
    config = load_config(DEFAULT_CONFIG)

    assert config.seed == 42
    assert config.reference_date == date(2026, 1, 1)
    assert config.currency == "BRL"
    assert config.output.directory == Path("data/output")
    assert config.output.format == "csv"
    assert config.accounts.initial_balance.min == Decimal("100.00")
    assert config.accounts.initial_balance.max == Decimal("50000.00")
    assert config.transactions.fraud_rate_overall == Decimal("0.005")


def test_rejects_missing_config_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigError, match="Não foi possível ler a configuração"):
        load_config(missing_path)


def test_rejects_yaml_root_that_is_not_an_object(tmp_path: Path) -> None:
    path = write_config(tmp_path, ["not", "an", "object"])

    with pytest.raises(ConfigError, match="'config': deve ser um objeto"):
        load_config(path)


def test_rejects_unsupported_currency(
    tmp_path: Path, valid_config: dict[str, object]
) -> None:
    config = deepcopy(valid_config)
    config["currency"] = "USD"

    with pytest.raises(ConfigError, match="'currency': deve ser um de: BRL"):
        load_config(write_config(tmp_path, config))


def test_rejects_unsupported_output_format(
    tmp_path: Path, valid_config: dict[str, object]
) -> None:
    config = deepcopy(valid_config)
    output = config["output"]
    assert isinstance(output, dict)
    output["format"] = "parquet"

    with pytest.raises(ConfigError, match="'output.format': deve ser um de: csv"):
        load_config(write_config(tmp_path, config))


def test_rejects_empty_output_directory(
    tmp_path: Path, valid_config: dict[str, object]
) -> None:
    config = deepcopy(valid_config)
    output = config["output"]
    assert isinstance(output, dict)
    output["directory"] = ""

    with pytest.raises(
        ConfigError, match="'output.directory': deve ser uma string não vazia"
    ):
        load_config(write_config(tmp_path, config))


@pytest.mark.parametrize(
    ("section", "field", "message"),
    [
        (None, "seed", "propriedades obrigatórias ausentes: seed"),
        ("output", "format", "propriedades obrigatórias ausentes: format"),
        (
            "accounts",
            "initial_balance",
            "propriedades obrigatórias ausentes: initial_balance",
        ),
        ("transactions", "count", "propriedades obrigatórias ausentes: count"),
    ],
)
def test_rejects_missing_required_fields(
    tmp_path: Path,
    valid_config: dict[str, object],
    section: str | None,
    field: str,
    message: str,
) -> None:
    config = deepcopy(valid_config)
    target = config if section is None else config[section]
    assert isinstance(target, dict)
    del target[field]

    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, config))


def test_rejects_unknown_nested_property(
    tmp_path: Path, valid_config: dict[str, object]
) -> None:
    config = deepcopy(valid_config)
    transactions = config["transactions"]
    assert isinstance(transactions, dict)
    transactions["unexpected"] = True

    with pytest.raises(ConfigError, match="propriedades desconhecidas: unexpected"):
        load_config(write_config(tmp_path, config))


def test_rejects_unknown_root_property(
    tmp_path: Path, valid_config: dict[str, object]
) -> None:
    config = deepcopy(valid_config)
    config["credentials"] = "not-allowed"

    with pytest.raises(ConfigError, match="propriedades desconhecidas: credentials"):
        load_config(write_config(tmp_path, config))


@pytest.mark.parametrize("rate", [-0.01, 1.01, "NaN", "Infinity"])
def test_rejects_rate_outside_closed_unit_interval(
    tmp_path: Path, valid_config: dict[str, object], rate: object
) -> None:
    config = deepcopy(valid_config)
    transactions = config["transactions"]
    assert isinstance(transactions, dict)
    transactions["declined_rate_overall"] = rate

    with pytest.raises(ConfigError, match="deve estar entre 0 e 1, inclusive"):
        load_config(write_config(tmp_path, config))


@pytest.mark.parametrize("rate", [0, 1])
def test_accepts_rate_at_closed_interval_boundary(
    tmp_path: Path, valid_config: dict[str, object], rate: int
) -> None:
    config = deepcopy(valid_config)
    transactions = config["transactions"]
    assert isinstance(transactions, dict)
    transactions["declined_rate_overall"] = rate

    loaded = load_config(write_config(tmp_path, config))

    assert loaded.transactions.declined_rate_overall == Decimal(rate)


@pytest.mark.parametrize(
    ("section", "field"),
    [("customers", "count"), ("accounts", "min_per_customer")],
)
def test_rejects_negative_integer(
    tmp_path: Path,
    valid_config: dict[str, object],
    section: str,
    field: str,
) -> None:
    config = deepcopy(valid_config)
    target = config[section]
    assert isinstance(target, dict)
    target[field] = -1

    with pytest.raises(ConfigError, match="deve ser maior ou igual a 0"):
        load_config(write_config(tmp_path, config))


@pytest.mark.parametrize("amount", [100, "100", "100.0", "-1.00"])
def test_rejects_money_not_encoded_as_non_negative_two_decimal_string(
    tmp_path: Path, valid_config: dict[str, object], amount: object
) -> None:
    config = deepcopy(valid_config)
    accounts = config["accounts"]
    assert isinstance(accounts, dict)
    initial_balance = accounts["initial_balance"]
    assert isinstance(initial_balance, dict)
    initial_balance["min"] = amount

    with pytest.raises(ConfigError, match="string monetária"):
        load_config(write_config(tmp_path, config))


@pytest.mark.parametrize(
    ("minimum_path", "maximum_path", "minimum", "maximum"),
    [
        ("min_per_customer", "max_per_customer", 4, 3),
        ("initial_balance.min", "initial_balance.max", "50000.01", "50000.00"),
    ],
)
def test_rejects_minimum_greater_than_maximum(
    tmp_path: Path,
    valid_config: dict[str, object],
    minimum_path: str,
    maximum_path: str,
    minimum: object,
    maximum: object,
) -> None:
    config = deepcopy(valid_config)
    accounts = config["accounts"]
    assert isinstance(accounts, dict)
    if minimum_path.startswith("initial_balance"):
        target = accounts["initial_balance"]
        assert isinstance(target, dict)
        target["min"] = minimum
        target["max"] = maximum
    else:
        accounts[minimum_path] = minimum
        accounts[maximum_path] = maximum

    with pytest.raises(ConfigError, match="deve ser menor ou igual"):
        load_config(write_config(tmp_path, config))


def test_rejects_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("accounts: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="YAML inválido"):
        load_config(path)


def test_safe_loader_rejects_python_object_tag(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "!!python/object/apply:builtins.str [unsafe]",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="YAML inválido"):
        load_config(path)


def test_rejects_invalid_reference_date(
    tmp_path: Path, valid_config: dict[str, object]
) -> None:
    config = deepcopy(valid_config)
    config["reference_date"] = "2026-02-30"

    with pytest.raises(ConfigError, match="data ISO válida"):
        load_config(write_config(tmp_path, config))
