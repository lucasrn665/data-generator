"""Resolução segura e determinística dos caminhos de exportação."""

from dataclasses import dataclass
from pathlib import Path

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.version import BATCH_SCHEMA_VERSION

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class UnsafeOutputPath(ValueError):
    """Indica que o destino configurado não é seguro para escrita."""


@dataclass(frozen=True, slots=True)
class BatchCsvPaths:
    """Caminhos finais gerenciados pela exportação batch."""

    directory: Path
    customers: Path
    addresses: Path
    accounts: Path
    cards: Path
    merchants: Path
    transactions: Path
    transaction_labels: Path
    transfers: Path
    ledger_entries: Path
    manifest: Path


def build_batch_csv_paths(
    config: BankingDataGeneratorConfig,
    *,
    project_root: Path = PROJECT_ROOT,
) -> BatchCsvPaths:
    """Construa os caminhos finais após validar o destino configurado."""
    root = project_root.resolve()
    base = _resolve_safe_base(config.output.directory, root)
    directory = (
        base
        / f"schema_version={BATCH_SCHEMA_VERSION}"
        / f"reference_date={config.reference_date.isoformat()}"
        / f"seed={config.seed}"
        / "scenario=valid"
    )
    return BatchCsvPaths(
        directory=directory,
        customers=directory / "customers.csv",
        addresses=directory / "addresses.csv",
        accounts=directory / "accounts.csv",
        cards=directory / "cards.csv",
        merchants=directory / "merchants.csv",
        transactions=directory / "transactions.csv",
        transaction_labels=directory / "transaction_labels.csv",
        transfers=directory / "transfers.csv",
        ledger_entries=directory / "ledger_entries.csv",
        manifest=directory / "manifest.json",
    )


def _resolve_safe_base(configured: Path, root: Path) -> Path:
    display_path = str(configured)
    if configured.is_absolute():
        _reject(display_path, "o diretório deve ser relativo à raiz do projeto")
    if ".." in configured.parts:
        _reject(display_path, "componentes '..' não são permitidos")

    candidate = (root / configured).resolve()
    if candidate == root:
        _reject(display_path, "o destino não pode ser a raiz do projeto")
    if not candidate.is_relative_to(root):
        _reject(display_path, "a resolução escapa da raiz do projeto")

    for protected_name in ("src", ".git"):
        protected = (root / protected_name).resolve()
        if candidate == protected or candidate.is_relative_to(protected):
            _reject(
                display_path, f"o destino não pode ficar dentro de '{protected_name}/'"
            )

    return candidate


def _reject(path: str, reason: str) -> None:
    raise UnsafeOutputPath(f"Diretório de saída rejeitado '{path}': {reason}.")
