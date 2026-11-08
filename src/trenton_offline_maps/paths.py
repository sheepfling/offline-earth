"""Public filesystem inputs normalize to pathlib.Path at the I/O boundary."""
from os import PathLike
from pathlib import Path
from typing import TypeAlias

PathInput: TypeAlias = str | PathLike[str]


def input_path(value: PathInput) -> Path:
    return Path(value)


def output_path(value: PathInput) -> Path:
    path = Path(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
