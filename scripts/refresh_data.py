"""Refresh Azure Updates and compose separately stored manual field overrides."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .catalog import ROOT, parse_catalog
from .feed import ENDPOINT, fetch_page, fetch_retirements, merge_retirements
from .manual_data import compose_catalog, read_overrides


def read_snapshot(output):
    try:
        return output.read_bytes()
    except FileNotFoundError:
        return None


def refresh_catalog(fetcher=fetch_page, output=ROOT / "data" / "retirements.json", db_dir=None):
    output = Path(output)
    fetched = fetch_retirements(fetcher)
    original = read_snapshot(output)
    previous = json.loads(original) if original is not None else None
    if original is not None and (not isinstance(previous, dict) or previous.get("schemaVersion") != 2):
        raise ValueError("Unsupported catalog schema; existing snapshot preserved")
    if previous is not None:
        parse_catalog(previous)
    records = merge_retirements(fetched, previous.get("records") if previous is not None else [])
    catalog = {
        "schemaVersion": 2, "source": ENDPOINT,
        "retrievedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "records": records,
    }
    manual = (Path(db_dir) if db_dir is not None else output.parent / "pipeline") / "manual.sqlite"
    if not manual.exists() and previous is not None and any(
        "manualEnrichment" in record for record in previous["records"]
    ):
        raise ValueError("Missing manual.sqlite for composed content; restore the manual database")
    overrides = read_overrides(manual)
    catalog = compose_catalog(catalog, overrides)
    if read_overrides(manual) != overrides:
        raise ValueError("Manual content changed during refresh; existing snapshot preserved")
    write_snapshot(catalog, output, original)
    return catalog


def write_snapshot(catalog, output, original, operation="refresh"):
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


if __name__ == "__main__":
    catalog = refresh_catalog()
    manual = sum("manualEnrichment" in record for record in catalog["records"])
    print(f"Saved {len(catalog['records'])} retirement announcements ({manual} with manual field overrides).")
