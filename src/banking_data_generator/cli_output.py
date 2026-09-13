"""Apresentação leve e centralizada da execução da CLI."""

import sys
from collections.abc import Callable


class CliReporter:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet

    def progress(self, message: str) -> None:
        if not self.quiet:
            print(message, file=sys.stderr, flush=True)

    def callback(self) -> Callable[[str], None]:
        return self.progress

    def error(self, message: str) -> None:
        print(message, file=sys.stderr, flush=True)
