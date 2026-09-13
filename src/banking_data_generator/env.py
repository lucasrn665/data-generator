"""Carregamento seguro e opcional de arquivos dotenv."""

import os
from pathlib import Path


class EnvFileError(ValueError):
    """Arquivo dotenv explicitamente solicitado e indisponível."""


def load_environment_file(path: Path, *, required: bool) -> None:
    """Carregue variáveis sem substituir as já presentes no processo."""
    if not path.is_file():
        if required:
            raise EnvFileError(f"arquivo .env não encontrado: '{path}'")
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_minimal_dotenv(path)
    else:
        load_dotenv(path, override=False)


def _load_minimal_dotenv(path: Path) -> None:
    """Fallback mínimo para ambientes de desenvolvimento sem a dependência instalada."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise EnvFileError(f"não foi possível ler o arquivo .env '{path}'") from error
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("\"'")
