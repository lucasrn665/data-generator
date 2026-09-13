"""Interface de linha de comando do pipeline batch."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import pyarrow as pa

from banking_data_generator.accounting import AccountingError
from banking_data_generator.config import ConfigError, load_config
from banking_data_generator.export import ManifestValidationError, UnsafeOutputPath
from banking_data_generator.pipeline import (
    BatchPipelineResult,
    DatasetValidationError,
    run_batch_pipeline,
)
from banking_data_generator.validation import ExtendedDomainValidationError


class CliInputError(ValueError):
    """Indica uma entrada inválida específica da CLI."""


def build_parser() -> argparse.ArgumentParser:
    """Construa o parser público da linha de comando."""
    parser = argparse.ArgumentParser(
        prog="python -m banking_data_generator",
        description=("Gera o domínio bancário sintético atual em seis arquivos CSV."),
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="caminho do arquivo YAML de configuração",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="raiz do projeto usada para resolver caminhos relativos (padrão: atual)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a CLI e retorne seu código de saída."""
    arguments = build_parser().parse_args(argv)
    try:
        project_root = arguments.project_root.resolve()
        if not project_root.is_dir():
            raise CliInputError(
                f"A raiz do projeto não existe ou não é diretório: '{project_root}'."
            )
        config_path = arguments.config
        if not config_path.is_absolute():
            config_path = project_root / config_path
        config = load_config(config_path)
        result = run_batch_pipeline(config, project_root)
    except (
        CliInputError,
        AccountingError,
        ConfigError,
        DatasetValidationError,
        ExtendedDomainValidationError,
        ManifestValidationError,
        UnsafeOutputPath,
        OSError,
        pa.ArrowException,
    ) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2

    print_success_summary(result)
    return 0


def print_success_summary(result: BatchPipelineResult) -> None:
    """Mostre somente metadados seguros da execução concluída."""
    print("status: sucesso")
    print(f"seed: {result.seed}")
    print(f"data de referência: {result.reference_date.isoformat()}")
    print(f"clientes: {result.customer_count}")
    print(f"endereços: {result.address_count}")
    print(f"contas: {result.account_count}")
    print(f"cartões: {result.card_count}")
    print(f"estabelecimentos: {result.merchant_count}")
    print(f"lançamentos: {result.ledger_entry_count}")
    print(f"créditos de abertura: {result.opening_credit_total:.2f} BRL")
    print(f"versão do gerador: {result.generator_version}")
    print(f"versão do schema: {result.schema_version}")
    publication = "criada" if result.created else "idempotente já existente"
    print(f"publicação: {publication}")
    print(f"diretório de saída: {result.output_directory}")
    print(
        "arquivos: "
        f"{result.customers_file.name}, "
        f"{result.addresses_file.name}, "
        f"{result.accounts_file.name}, "
        f"{result.cards_file.name}, "
        f"{result.merchants_file.name}, "
        f"{result.ledger_entries_file.name}, "
        f"{result.manifest_file.name}"
    )
