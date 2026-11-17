"""Atomic, guarded writes for the public JSON catalog."""

import json
import os
import tempfile
from pathlib import Path

from .catalog import parse_catalog


def read_snapshot(output):
    try:
        return Path(output).read_bytes()
    except FileNotFoundError:
        return None


def write_snapshot(catalog, output, original, operation="write"):
    parse_catalog(catalog)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output.parent,
            prefix=output.name + ".", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(catalog, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if read_snapshot(output) != original:
            raise ValueError(f"Catalog changed during {operation}; existing snapshot preserved. Retry the {operation}.")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
