"""Construção e validação do manifesto determinístico de execução."""

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pa_csv

from banking_data_generator.config import BankingDataGeneratorConfig
from banking_data_generator.version import BATCH_SCHEMA_VERSION, GENERATOR_VERSION

CSV_ENTITY_FILES = {
    "accounts": "accounts.csv",
    "addresses": "addresses.csv",
    "customers": "customers.csv",
    "cards": "cards.csv",
    "merchants": "merchants.csv",
    "transactions": "transactions.csv",
    "transaction_labels": "transaction_labels.csv",
    "transfers": "transfers.csv",
    "ledger_entries": "ledger_entries.csv",
}
MANAGED_FILENAMES = frozenset({*CSV_ENTITY_FILES.values(), "manifest.json"})


class ManifestValidationError(ValueError):
    """Indica manifesto ou conjunto publicado inválido."""


def build_manifest(
    config: BankingDataGeneratorConfig,
    directory: Path,
    record_counts: Mapping[str, int],
    accounting_invariants: Mapping[str, int | str],
    domain_summary: Mapping[str, Any],
    transaction_summary: Mapping[str, Any],
    transfer_summary: Mapping[str, Any],
    fraud_label_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Construa o manifesto a partir dos CSVs já escritos e validados."""
    files = {
        filename: {
            "path": filename,
            "record_count": record_counts[entity],
            "sha256": _sha256(directory / filename),
            "size_bytes": (directory / filename).stat().st_size,
        }
        for entity, filename in CSV_ENTITY_FILES.items()
    }
    return {
        "accounting_invariants": dict(accounting_invariants),
        "currency": config.currency,
        "domain_summary": dict(domain_summary),
        "expected_violation_count": 0,
        "files": files,
        "generator_version": GENERATOR_VERSION,
        "parameters": {
            "accounts": {
                "initial_balance": {
                    "max": str(config.accounts.initial_balance.max),
                    "min": str(config.accounts.initial_balance.min),
                },
                "max_per_customer": config.accounts.max_per_customer,
                "min_per_customer": config.accounts.min_per_customer,
            },
            "customers": {"count": config.customers.count},
            "cards": {
                "per_account": config.cards.per_account,
                "daily_purchase_limit": {
                    "min": str(config.cards.daily_purchase_limit.min),
                    "max": str(config.cards.daily_purchase_limit.max),
                },
                "initially_blocked_rate": str(config.cards.initially_blocked_rate),
            },
            "merchants": {"count": config.merchants.count},
            "transactions": {
                "count": config.transactions.count,
                "purchase_amount": {
                    "min": str(config.transactions.purchase_amount.min),
                    "max": str(config.transactions.purchase_amount.max),
                },
                "history_days": config.transactions.history_days,
                "declined_rate_overall": str(config.transactions.declined_rate_overall),
                "fraud_rate_overall": str(config.transactions.fraud_rate_overall),
            },
            "transfers": {
                "count": config.transfers.count,
                "min_amount": str(config.transfers.min_amount),
                "max_amount": str(config.transfers.max_amount),
                "declined_rate_overall": str(config.transfers.declined_rate_overall),
                "history_days": config.transfers.history_days,
            },
            "output_format": config.output.format,
        },
        "quality_scenarios": [],
        "reference_date": config.reference_date.isoformat(),
        "scenario": "valid",
        "schema_version": BATCH_SCHEMA_VERSION,
        "seed": config.seed,
        "transaction_summary": dict(transaction_summary),
        "transfer_summary": dict(transfer_summary),
        "fraud_label_summary": dict(fraud_label_summary),
    }


def serialize_manifest(manifest: Mapping[str, Any]) -> bytes:
    """Serialize JSON UTF-8 com ordem, indentação e terminação estáveis."""
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    return f"{text}\n".encode()


def validate_csv_files(directory: Path, manifest: Mapping[str, Any]) -> None:
    """Valide presença, contagem, tamanho e checksum dos nove CSVs."""
    files = manifest.get("files")
    if not isinstance(files, dict):
        _fail("a propriedade 'files' é inválida")

    for entity, filename in CSV_ENTITY_FILES.items():
        path = directory / filename
        if not path.is_file():
            _fail(f"o arquivo obrigatório '{filename}' está ausente")
        metadata = files.get(filename)
        if not isinstance(metadata, dict):
            _fail(f"os metadados de '{filename}' são inválidos")
        if metadata.get("path") != filename:
            _fail(f"o caminho relativo de '{filename}' é inválido")
        if metadata.get("size_bytes") != path.stat().st_size:
            _fail(f"o tamanho de '{filename}' é divergente")
        if metadata.get("sha256") != _sha256(path):
            _fail(f"o checksum de '{filename}' é divergente")
        try:
            actual_count = pa_csv.read_csv(path).num_rows
        except (OSError, pa.ArrowException) as error:
            raise ManifestValidationError(
                f"Execução publicada inválida: não foi possível ler '{filename}'."
            ) from error
        if metadata.get("record_count") != actual_count:
            _fail(f"a contagem de registros de '{entity}' é divergente")


def load_manifest(path: Path) -> dict[str, Any]:
    """Carregue um manifesto existente com erros de domínio legíveis."""
    if not path.is_file():
        _fail("o arquivo obrigatório 'manifest.json' está ausente")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestValidationError(
            "Execução publicada inválida: 'manifest.json' não é um JSON UTF-8 válido."
        ) from error
    if not isinstance(value, dict):
        _fail("a raiz de 'manifest.json' deve ser um objeto")
    return value


def validate_existing_publication(
    directory: Path,
    expected_manifest: Mapping[str, Any],
) -> None:
    """Garanta que uma publicação existente coincide exatamente com a solicitada."""
    if not directory.is_dir():
        _fail(f"o destino existente '{directory.name}' não é um diretório")
    actual_names = {path.name for path in directory.iterdir()}
    if actual_names != MANAGED_FILENAMES:
        _fail("o diretório final não contém exatamente os dez arquivos esperados")

    manifest_path = directory / "manifest.json"
    existing_manifest = load_manifest(manifest_path)
    if existing_manifest != expected_manifest:
        _fail("o manifesto existente é incompatível com a execução solicitada")
    if manifest_path.read_bytes() != serialize_manifest(expected_manifest):
        _fail("a serialização do manifesto existente é divergente")
    validate_csv_files(directory, existing_manifest)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fail(message: str) -> None:
    raise ManifestValidationError(f"Execução publicada inválida: {message}.")
