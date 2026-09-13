from pathlib import Path

import pytest

from banking_data_generator.env import EnvFileError, load_environment_file


def test_process_environment_takes_precedence(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BANKING_GENERATOR_EVENT_HUBS_ENABLED=false\n", encoding="utf-8"
    )
    monkeypatch.setenv("BANKING_GENERATOR_EVENT_HUBS_ENABLED", "true")
    load_environment_file(env_file, required=True)
    assert __import__("os").environ["BANKING_GENERATOR_EVENT_HUBS_ENABLED"] == "true"


def test_default_missing_file_is_allowed(tmp_path: Path) -> None:
    load_environment_file(tmp_path / ".env", required=False)


def test_explicit_missing_file_is_friendly(tmp_path: Path) -> None:
    with pytest.raises(EnvFileError, match="arquivo .env não encontrado"):
        load_environment_file(tmp_path / "missing.env", required=True)
