"""Publicação opcional e segura de um conjunto batch no ADLS Gen2."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Protocol

from banking_data_generator.config import AdlsConfig
from banking_data_generator.export.manifest import (
    load_manifest,
    serialize_manifest,
    validate_csv_files,
)


class RemotePublicationError(RuntimeError):
    """Erro legível durante autenticação, upload ou promoção remota."""


@dataclass(frozen=True, slots=True)
class RemotePublicationResult:
    state: str
    path: str
    file_count: int
    phase_durations: dict[str, float] | None = None


class RemoteBatchDestination(Protocol):
    def publish(
        self, local_directory: Path, relative_directory: str, overwrite: bool = False
    ) -> RemotePublicationResult: ...


def validate_local_publication(local_directory: Path) -> dict:
    """Valide o conjunto local antes de qualquer chamada remota."""
    manifest = load_manifest(local_directory / "manifest.json")
    validate_csv_files(local_directory, manifest)
    return manifest


class AzureAdlsDestination:
    """Destino real usando DefaultAzureCredential e o SDK oficial do ADLS."""

    def __init__(self, config: AdlsConfig) -> None:
        self.config = config

    def publish(
        self, local_directory: Path, relative_directory: str, overwrite: bool = False
    ) -> RemotePublicationResult:
        manifest = validate_local_publication(local_directory)
        credential = None
        service = None
        phase_durations: dict[str, float] = {}
        try:
            from azure.core.exceptions import AzureError, ResourceExistsError
            from azure.identity import DefaultAzureCredential
            from azure.storage.filedatalake import DataLakeServiceClient
        except ImportError as error:
            raise RemotePublicationError(
                "SDKs Azure não estão instalados; instale azure-identity e "
                "azure-storage-file-datalake."
            ) from error
        try:
            credential = DefaultAzureCredential()
            service = DataLakeServiceClient(
                account_url=self.config.account_url, credential=credential
            )
            filesystem = service.get_file_system_client(self.config.file_system)
            final = _join(self.config.base_directory, relative_directory)
            staging = (
                f"{final}.staging-SYN-{manifest['seed']}-{manifest['reference_date']}"
            )
            final_exists = _directory_exists(filesystem, final)
            if final_exists:
                if _remote_matches(filesystem, final, manifest):
                    return RemotePublicationResult(
                        "idempotent", final, len(manifest["files"])
                    )
                if overwrite:
                    raise RemotePublicationError(
                        "substituição ADLS não é suportada com segurança pelo SDK; "
                        "preserve o destino existente ou use um novo caminho"
                    )
                raise RemotePublicationError(
                    f"publicação remota divergente já existe em '{final}'"
                )
            _ensure_parent_directories(filesystem, final, ResourceExistsError)
            directory = filesystem.get_directory_client(staging)
            directory.create_directory()
            filenames = sorted(manifest["files"])
            started = monotonic()
            _upload_csv_files(
                directory, local_directory, filenames, self.config.max_concurrency
            )
            phase_durations["upload"] = monotonic() - started
            _upload_file(directory, "manifest.json", local_directory / "manifest.json")
            started = monotonic()
            if not _remote_matches(filesystem, staging, manifest):
                raise RemotePublicationError("validação remota do staging falhou")
            phase_durations["validation"] = monotonic() - started
            started = monotonic()
            directory.rename_directory(new_name=f"{self.config.file_system}/{final}")
            phase_durations["promotion"] = monotonic() - started
            return RemotePublicationResult(
                "created", final, len(filenames) + 1, phase_durations
            )
        except RemotePublicationError:
            _cleanup_remote_staging(locals().get("filesystem"), locals().get("staging"))
            raise
        except (AzureError, OSError, TimeoutError, ConnectionError) as error:
            _cleanup_remote_staging(locals().get("filesystem"), locals().get("staging"))
            raise RemotePublicationError(
                f"falha na publicação ADLS: {error}"
            ) from error
        finally:
            for client in (service, credential):
                if client is not None and hasattr(client, "close"):
                    try:
                        client.close()
                    except Exception:
                        pass


def remote_batch_path(local_directory: Path) -> str:
    """Converta o caminho local para o layout remoto sem schema ou seed."""
    parts = list(local_directory.parts)
    try:
        index = next(
            i for i, part in enumerate(parts) if part.startswith("schema_version=")
        )
    except StopIteration as error:
        raise RemotePublicationError(
            "caminho local não contém partição de schema"
        ) from error
    relative = parts[index:]
    try:
        reference = next(
            part for part in relative if part.startswith("reference_date=")
        )
        scenario_index = next(
            i for i, part in enumerate(relative) if part.startswith("scenario=")
        )
        scenario = relative[scenario_index].removeprefix("scenario=")
    except StopIteration as error:
        raise RemotePublicationError(
            "caminho local não contém referência e cenário"
        ) from error
    if scenario == "valid":
        return f"{reference}/valid"
    return f"{reference}/invalid/{scenario}"


def _join(base: str, relative: str) -> str:
    return "/".join(part.strip("/") for part in (base, relative) if part)


def _ensure_parent_directories(
    filesystem: object, final: str, resource_exists_error: type[Exception]
) -> None:
    """Crie somente os pais ausentes, sem criar o diretório final."""
    segments = [segment for segment in final.split("/") if segment]
    for index in range(1, len(segments)):
        path = "/".join(segments[:index])
        try:
            filesystem.get_directory_client(path).create_directory()
        except resource_exists_error:
            continue


def _upload_file(directory: object, filename: str, local: Path) -> None:
    client = directory.get_file_client(filename)
    with local.open("rb") as stream:
        client.upload_data(stream, overwrite=True)


def _upload_csv_files(
    directory: object, local_directory: Path, filenames: list[str], max_workers: int
) -> None:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _upload_file, directory, filename, local_directory / filename
            ): filename
            for filename in filenames
        }
        for future in as_completed(futures):
            try:
                future.result()
            except BaseException:
                for pending in futures:
                    pending.cancel()
                raise


def _directory_exists(filesystem: object, path: str) -> bool:
    try:
        filesystem.get_directory_client(path).get_directory_properties()
        return True
    except Exception as error:
        if error.__class__.__name__ in {"ResourceNotFoundError", "NotFoundError"}:
            return False
        raise


def _cleanup_remote_staging(filesystem: object, staging: object) -> None:
    if (
        filesystem is None
        or not isinstance(staging, str)
        or ".staging-SYN-" not in staging
    ):
        return
    try:
        filesystem.delete_directory(staging)
    except Exception as error:
        if error.__class__.__name__ not in {"ResourceNotFoundError", "NotFoundError"}:
            return


def _remote_matches(filesystem: object, path: str, manifest: dict) -> bool:
    try:
        directory = filesystem.get_directory_client(path)
        remote_manifest = _download(directory, "manifest.json")
        if remote_manifest != serialize_manifest(manifest):
            return False
        with ThreadPoolExecutor(
            max_workers=min(16, max(1, len(manifest["files"])))
        ) as executor:
            futures = {
                executor.submit(_stream_digest, directory, filename): (
                    filename,
                    metadata,
                )
                for filename, metadata in manifest["files"].items()
            }
            for future in as_completed(futures):
                _, metadata = futures[future]
                size, digest = future.result()
                if size != metadata["size_bytes"] or digest != metadata["sha256"]:
                    return False
        return True
    except Exception as error:
        if error.__class__.__name__ in {"ResourceNotFoundError", "NotFoundError"}:
            return False
        raise


def _download(directory: object, filename: str) -> bytes:
    response = directory.get_file_client(filename).download_file()
    return response.readall()


def _stream_digest(directory: object, filename: str) -> tuple[int, str]:
    response = directory.get_file_client(filename).download_file()
    digest = sha256()
    size = 0
    for chunk in response.chunks():
        digest.update(chunk)
        size += len(chunk)
    return size, digest.hexdigest()
