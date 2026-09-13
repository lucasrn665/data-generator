"""Conversão e escrita batch dos dados sintéticos."""

from banking_data_generator.export.adls import (
    AzureAdlsDestination,
    RemoteBatchDestination,
    RemotePublicationError,
    RemotePublicationResult,
    remote_batch_path,
)
from banking_data_generator.export.csv_writer import (
    BatchPublicationResult,
    write_batch_csv,
)
from banking_data_generator.export.event_hubs import (
    AzureEventHubsDestination,
    EventHubsDestination,
    EventHubsPublicationError,
    EventHubsPublicationResult,
)
from banking_data_generator.export.manifest import ManifestValidationError
from banking_data_generator.export.paths import BatchCsvPaths, UnsafeOutputPath
from banking_data_generator.export.tables import (
    accounts_to_table,
    addresses_to_table,
    cards_to_table,
    customers_to_table,
    ledger_entries_to_table,
    merchants_to_table,
    transaction_labels_to_table,
    transactions_to_table,
    transfers_to_table,
)

__all__ = [
    "BatchCsvPaths",
    "BatchPublicationResult",
    "AzureAdlsDestination",
    "RemoteBatchDestination",
    "RemotePublicationError",
    "RemotePublicationResult",
    "remote_batch_path",
    "ManifestValidationError",
    "UnsafeOutputPath",
    "accounts_to_table",
    "addresses_to_table",
    "cards_to_table",
    "customers_to_table",
    "ledger_entries_to_table",
    "merchants_to_table",
    "transactions_to_table",
    "transaction_labels_to_table",
    "transfers_to_table",
    "write_batch_csv",
    "AzureEventHubsDestination",
    "EventHubsDestination",
    "EventHubsPublicationError",
    "EventHubsPublicationResult",
]
