from pathlib import Path

import pytest

import banking_data_generator.cli as cli_module

DEFAULT_CONFIG = Path(__file__).parents[1] / "configs" / "default.yaml"


@pytest.fixture
def cli_project(tmp_path: Path) -> Path:
    config_directory = tmp_path / "configs"
    config_directory.mkdir()
    contents = DEFAULT_CONFIG.read_text(encoding="utf-8")
    contents = contents.replace("directory: data/output", "directory: output")
    contents = contents.replace("count: 10000", "count: 4", 1)
    (config_directory / "test.yaml").write_text(contents, encoding="utf-8")
    return tmp_path


def test_help_is_clear_and_successful(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        cli_module.main(["--help"])

    assert raised.value.code == 0
    output = capsys.readouterr().out
    assert "--config" in output
    assert "--project-root" in output
    assert "clientes, endereços e contas" in output


def test_missing_required_argument_returns_argparse_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        cli_module.main([])

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert "--config" in error
    assert "Traceback" not in error


def test_valid_cli_run_prints_summary_and_preserves_cwd(
    cli_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(cli_project)
    original_cwd = Path.cwd()

    exit_code = cli_module.main(["--config", "configs/test.yaml"])

    assert exit_code == 0
    assert Path.cwd() == original_cwd
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "status: sucesso" in captured.out
    assert "seed: 42" in captured.out
    assert "data de referência: 2026-01-01" in captured.out
    assert "clientes: 4" in captured.out
    assert "endereços: 4" in captured.out
    assert "versão do gerador: 0.1.0" in captured.out
    assert "versão do schema: 1.0.0" in captured.out
    assert "publicação: criada" in captured.out
    assert "customers.csv, addresses.csv, accounts.csv, manifest.json" in captured.out
    assert "SYN-CUS-" not in captured.out

    directory = (
        cli_project / "output" / "reference_date=2026-01-01" / "seed=42" / "valid"
    )
    assert {path.name for path in directory.glob("*.csv")} == {
        "customers.csv",
        "addresses.csv",
        "accounts.csv",
    }
    assert (directory / "manifest.json").is_file()

    assert cli_module.main(["--config", "configs/test.yaml"]) == 0
    assert "publicação: idempotente já existente" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("config_name", "replacement", "expected"),
    [
        ("missing.yaml", None, "Não foi possível ler"),
        ("invalid.yaml", ("seed: 42", "seed: invalid"), "Configuração inválida"),
        (
            "unsafe.yaml",
            ("directory: data/output", "directory: src/output"),
            "Diretório de saída rejeitado",
        ),
    ],
)
def test_expected_errors_are_readable_without_traceback(
    tmp_path: Path,
    config_name: str,
    replacement: tuple[str, str] | None,
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if replacement is not None:
        contents = DEFAULT_CONFIG.read_text(encoding="utf-8")
        (tmp_path / config_name).write_text(
            contents.replace(*replacement), encoding="utf-8"
        )

    exit_code = cli_module.main(
        ["--config", config_name, "--project-root", str(tmp_path)]
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert expected in captured.err
    assert "Traceback" not in captured.err


def test_unexpected_defect_is_not_masked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(DEFAULT_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")

    def fail_unexpectedly(path: Path) -> None:
        raise RuntimeError("unexpected defect")

    monkeypatch.setattr(cli_module, "load_config", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="unexpected defect"):
        cli_module.main(["--config", str(config_path), "--project-root", str(tmp_path)])
