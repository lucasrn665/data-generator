import sys
import types
from dataclasses import replace
from pathlib import Path

from banking_data_generator.config import AdlsConfig, load_config
from banking_data_generator.export import AzureAdlsDestination, remote_batch_path
from banking_data_generator.pipeline import run_batch_pipeline

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "default.yaml"


class _File:
    def __init__(self, directory: _Directory, name: str) -> None:
        self.directory, self.name = directory, name

    def upload_data(self, stream: object, overwrite: bool = False) -> None:
        self.directory.files[self.name] = stream.read()
        self.directory.order.append(self.name)

    def download_file(self) -> _Download:
        return _Download(self.directory.files[self.name])


class _Download:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def readall(self) -> bytes:
        return self.data


class _Directory:
    def __init__(self, filesystem: _Filesystem, path: str) -> None:
        self.filesystem, self.path = filesystem, path
        self.files = filesystem.directories.get(path, {})
        self.order: list[str] = []

    def create_directory(self) -> None:
        self.filesystem.directories[self.path] = self.files

    def get_file_client(self, name: str) -> _File:
        return _File(self, name)

    def get_directory_properties(self) -> dict[str, str]:
        if self.path not in self.filesystem.directories:
            raise type("ResourceNotFoundError", (Exception,), {})()
        return {}

    def rename_directory(self, final: str, overwrite: bool = False) -> None:
        if final in self.filesystem.directories and not overwrite:
            raise RuntimeError("conflict")
        self.filesystem.directories[final] = self.filesystem.directories.pop(self.path)


class _Filesystem:
    def __init__(self) -> None:
        self.directories: dict[str, dict[str, bytes]] = {}
        self.created: list[_Directory] = []

    def get_directory_client(self, path: str) -> _Directory:
        directory = _Directory(self, path)
        self.created.append(directory)
        return directory


def test_remote_batch_path_is_relative() -> None:
    path = Path(
        "/tmp/output/schema_version=1.7.2/reference_date=2026-01-01/seed=1/scenario=valid"
    )
    assert (
        remote_batch_path(path)
        == "schema_version=1.7.2/reference_date=2026-01-01/seed=1/scenario=valid"
    )


def test_adls_fake_uploads_manifest_last_and_promotes(
    monkeypatch, tmp_path: Path
) -> None:
    config = load_config(DEFAULT_CONFIG)
    config = replace(
        config,
        output=replace(config.output, directory=Path("output")),
        customers=replace(config.customers, count=2),
        merchants=replace(config.merchants, count=2),
        transactions=replace(config.transactions, count=2),
        transfers=replace(config.transfers, count=1),
    )
    publication = run_batch_pipeline(config, tmp_path)
    filesystem = _Filesystem()
    credential_created: list[bool] = []

    class Credential:
        def __init__(self) -> None:
            credential_created.append(True)

    class Service:
        def __init__(self, **kwargs: object) -> None:
            self.filesystem = filesystem

        def get_file_system_client(self, name: str) -> _Filesystem:
            return filesystem

    azure = types.ModuleType("azure")
    core = types.ModuleType("azure.core")
    exceptions = types.ModuleType("azure.core.exceptions")
    exceptions.AzureError = Exception
    identity = types.ModuleType("azure.identity")
    identity.DefaultAzureCredential = Credential
    storage = types.ModuleType("azure.storage")
    filedatalake = types.ModuleType("azure.storage.filedatalake")
    filedatalake.DataLakeServiceClient = Service
    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.core", core)
    monkeypatch.setitem(sys.modules, "azure.core.exceptions", exceptions)
    monkeypatch.setitem(sys.modules, "azure.identity", identity)
    monkeypatch.setitem(sys.modules, "azure.storage", storage)
    monkeypatch.setitem(sys.modules, "azure.storage.filedatalake", filedatalake)

    result = AzureAdlsDestination(
        AdlsConfig(
            enabled=True,
            account_url="https://example.dfs.core.windows.net",
            file_system="synthetic-data",
            base_directory="banking",
            overwrite=False,
        )
    ).publish(
        publication.output_directory, remote_batch_path(publication.output_directory)
    )

    assert result.state == "created"
    assert credential_created == [True]
    assert filesystem.directories
    assert all(
        directory.order[-1] == "manifest.json"
        for directory in filesystem.created
        if directory.order
    )
