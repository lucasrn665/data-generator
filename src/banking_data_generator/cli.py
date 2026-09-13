"""Interface de linha de comando do pipeline batch."""

import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pyarrow as pa

from banking_data_generator.accounting import AccountingError
from banking_data_generator.cli_output import CliReporter
from banking_data_generator.config import ConfigError, load_config
from banking_data_generator.env import EnvFileError, load_environment_file
from banking_data_generator.export import (
    AzureAdlsDestination,
    AzureEventHubsDestination,
    EventHubsPublicationError,
    ManifestValidationError,
    RemotePublicationError,
    UnsafeOutputPath,
    remote_batch_path,
)
from banking_data_generator.generation import TransferGenerationError
from banking_data_generator.pipeline import (
    BatchPipelineResult,
    DatasetValidationError,
    run_batch_pipeline,
)
from banking_data_generator.quality import QualityScenarioError
from banking_data_generator.validation import (
    ExtendedDomainValidationError,
    FraudLabelValidationError,
    ReversalValidationError,
    TransactionValidationError,
    TransferValidationError,
)


class CliInputError(ValueError):
    """Indica uma entrada inválida específica da CLI."""


_SCENARIOS = (
    "valid",
    "duplicate_exact",
    "duplicate_conflicting",
    "required_null",
    "orphan_foreign_key",
    "late_event",
    "schema_additive_column",
    "schema_missing_column",
    "schema_renamed_column",
    "schema_incompatible_value",
    "schema_unknown_enum",
)


def build_parser() -> argparse.ArgumentParser:
    """Construa o parser público da linha de comando."""
    parser = argparse.ArgumentParser(
        prog="python -m banking_data_generator",
        description=("Gera o domínio bancário sintético atual em nove arquivos CSV."),
    )
    parser.add_argument(
        "--publish-adls",
        action="store_true",
        help="publique a execução local no Azure Data Lake Storage Gen2",
    )
    parser.add_argument(
        "--publish-event-hubs",
        action="store_true",
        help="publique o replay financeiro opcional no Azure Event Hubs",
    )
    parser.add_argument(
        "--events-per-second",
        type=int,
        default=None,
        help="limite não secreto de eventos por segundo (0 = sem espera)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="caminho do arquivo YAML de configuração",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="arquivo dotenv (padrão: .env; ausente por padrão é permitido)",
    )
    parser.add_argument(
        "--scenario",
        choices=_SCENARIOS,
        default="valid",
        help="cenário de qualidade exclusivo a publicar (padrão: valid)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="raiz do projeto usada para resolver caminhos relativos (padrão: atual)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="mostre somente o resultado final e erros"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a CLI e retorne seu código de saída."""
    arguments = build_parser().parse_args(argv)
    reporter = CliReporter(arguments.quiet)
    stage = "configuração"
    try:
        reporter.progress("🔧 Carregando configuração...")
        project_root = arguments.project_root.resolve()
        env_path = arguments.env_file or (project_root / ".env")
        if not env_path.is_absolute():
            env_path = project_root / env_path
        load_environment_file(env_path, required=arguments.env_file is not None)
        if not project_root.is_dir():
            raise CliInputError(
                f"A raiz do projeto não existe ou não é diretório: '{project_root}'."
            )
        config_path = arguments.config
        if not config_path.is_absolute():
            config_path = project_root / config_path
        config = load_config(config_path)
        reporter.progress("✅ Configuração carregada")
        config = replace(
            config, quality=replace(config.quality, scenario=arguments.scenario)
        )
        reporter.progress("🏗️ Gerando dados sintéticos...")
        stage = "geração"
        result = run_batch_pipeline(config, project_root)
        reporter.progress("✅ Dados gerados")
        reporter.progress("🔍 Validando regras e reconciliação...")
        reporter.progress("✅ Validação concluída")
        reporter.progress("💾 Publicando arquivos localmente...")
        reporter.progress("✅ Publicação local concluída")
        remote = None
        if arguments.publish_adls:
            stage = "publicação ADLS"
            reporter.progress("☁️ Preparando publicação no ADLS...")
            if not config.adls.enabled:
                raise CliInputError("ADLS está desabilitado na configuração")
            remote = AzureAdlsDestination(config.adls).publish(
                result.output_directory,
                remote_batch_path(result.output_directory),
                config.adls.overwrite,
                progress=reporter.callback(),
            )
            reporter.progress("✅ ADLS concluído")
        event_hubs = None
        if arguments.publish_event_hubs:
            stage = "replay Event Hubs"
            reporter.progress("📨 Preparando replay para o Event Hubs...")
            if not config.event_hubs.enabled:
                raise CliInputError("Event Hubs está desabilitado na configuração")
            event_config = config.event_hubs
            if arguments.events_per_second is not None:
                if arguments.events_per_second < 0:
                    raise CliInputError("events-per-second deve ser maior ou igual a 0")
                event_config = replace(
                    event_config, events_per_second=arguments.events_per_second
                )
            event_hubs = AzureEventHubsDestination().publish(
                result.replay_events, event_config, progress=reporter.callback()
            )
            reporter.progress("✅ Replay concluído")
    except (
        CliInputError,
        AccountingError,
        ConfigError,
        DatasetValidationError,
        ExtendedDomainValidationError,
        FraudLabelValidationError,
        TransactionValidationError,
        ReversalValidationError,
        TransferValidationError,
        TransferGenerationError,
        ManifestValidationError,
        QualityScenarioError,
        UnsafeOutputPath,
        RemotePublicationError,
        EventHubsPublicationError,
        EnvFileError,
        OSError,
        pa.ArrowException,
    ) as error:
        reporter.error(f"❌ Falha em {stage}: {error}")
        return 2

    print_success_summary(result)
    if remote is not None:
        print(f"publicação ADLS: {remote.state}")
        print(f"destino ADLS: {remote.path}")
        print(f"arquivos ADLS: {remote.file_count}")
        if remote.phase_durations:
            for phase in ("upload", "validation", "promotion"):
                if phase in remote.phase_durations:
                    print(f"ADLS {phase}: {remote.phase_durations[phase]:.3f}s")
    if event_hubs is not None:
        print(f"publicação Event Hubs: {event_hubs.state}")
        print(f"eventos planejados: {event_hubs.events_planned}")
        print(f"eventos enviados: {event_hubs.events_sent}")
        print(f"lotes enviados: {event_hubs.batches}")
    return 0


def print_success_summary(result: BatchPipelineResult) -> None:
    """Mostre somente metadados seguros da execução concluída."""
    print("═" * 36)
    print("✅ Execução concluída")
    print("═" * 36)
    print("Execução")
    print("status: sucesso")
    print(f"seed: {result.seed}")
    print(f"data de referência: {result.reference_date.isoformat()}")
    print("Entidades geradas")
    print(f"clientes: {result.customer_count}")
    print(f"endereços: {result.address_count}")
    print(f"contas: {result.account_count}")
    print(f"cartões: {result.card_count}")
    print(f"estabelecimentos: {result.merchant_count}")
    print("Compras e estornos")
    print(f"tentativas de compra: {result.purchase_attempt_count}")
    print(f"compras aprovadas: {result.approved_transaction_count}")
    print(f"compras recusadas: {result.declined_transaction_count}")
    print(f"meta de recusas: {result.target_decline_count}")
    print(f"recusas planejadas: {result.planned_decline_count}")
    print(f"recusas adicionais: {result.additional_decline_count}")
    print(f"meta de estornos: {result.reversal_target_count}")
    print(f"estornos efetivos: {result.reversal_count}")
    print(f"eventos de transação: {result.transaction_event_count}")
    print(f"valor estornado: {result.reversed_amount_total:.2f} BRL")
    print(f"saldo agregado final: {result.final_balance_total:.2f} BRL")
    print("Transferências")
    print(f"tentativas de transferência: {result.transfer_attempt_count}")
    print(f"transferências concluídas: {result.completed_transfer_count}")
    print(f"transferências recusadas: {result.declined_transfer_count}")
    print(f"meta de recusas de transferência: {result.transfer_target_decline_count}")
    print(
        f"recusas planejadas de transferência: {result.transfer_planned_decline_count}"
    )
    print(
        "recusas adicionais de transferência: "
        f"{result.transfer_additional_decline_count}"
    )
    print(f"valor transferido: {result.completed_transfer_amount_total:.2f} BRL")
    print(
        "valor recusado em transferências: "
        f"{result.declined_transfer_amount_total:.2f} BRL"
    )
    print("Fraude e qualidade")
    print(f"meta de fraude sintética: {result.target_fraud_count}")
    print(f"fraudes sintéticas efetivas: {result.synthetic_fraud_count}")
    print(f"fraudes aprovadas: {result.approved_fraud_count}")
    print(f"fraudes recusadas: {result.declined_fraud_count}")
    patterns = ", ".join(
        f"{name}={count}"
        for name, count in sorted(result.fraud_count_by_pattern.items())
    )
    print(f"fraudes por padrão: {patterns or 'nenhuma'}")
    print(f"lançamentos: {result.ledger_entry_count}")
    print(f"créditos de abertura: {result.opening_credit_total:.2f} BRL")
    print(f"versão do gerador: {result.generator_version}")
    print(f"versão do schema: {result.schema_version}")
    print(f"cenário: {result.scenario}")
    print(f"entidade-alvo de qualidade: {result.quality_target_entity}")
    if result.quality_target_field is not None:
        print(f"campo-alvo de qualidade: {result.quality_target_field}")
    print(f"registros afetados: {result.quality_affected_count}")
    print(f"violações esperadas: {result.expected_violation_count}")
    print(f"meta de eventos atrasados: {result.target_late_event_count}")
    print(f"eventos atrasados observados: {result.observed_late_event_count}")
    print(
        "atraso observado (segundos): "
        f"{result.minimum_observed_delay_seconds}..{result.maximum_observed_delay_seconds}"
    )
    print("Publicação local")
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
        f"{result.transactions_file.name}, "
        f"{result.transaction_labels_file.name}, "
        f"{result.transfers_file.name}, "
        f"{result.ledger_entries_file.name}, "
        f"{result.manifest_file.name}"
    )
    print("═" * 36)
