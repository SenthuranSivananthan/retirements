"""Refresh the canonical snapshot, preserving complete manually enriched records."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .catalog import ROOT, parse_catalog
from .feed import ENDPOINT, fetch_page, fetch_retirements, merge_retirements


def read_snapshot(output):
    try:
        return output.read_bytes()
    except FileNotFoundError:
        return None


def refresh_catalog(fetcher=fetch_page, output=ROOT / "data" / "retirements.json"):
    output = Path(output)
    fetched = fetch_retirements(fetcher)
    original = read_snapshot(output)
    previous = json.loads(original) if original is not None else None
    if original is not None and (not isinstance(previous, dict) or previous.get("schemaVersion") != 2):
        raise ValueError("Unsupported catalog schema; existing snapshot preserved")
    records = merge_retirements(fetched, previous.get("records") if previous is not None else [])
    catalog = parse_catalog({
        "schemaVersion": 2, "source": ENDPOINT,
        "retrievedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "records": records,
    })
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
            raise ValueError("Catalog changed during refresh; existing snapshot preserved. Retry the refresh.")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return catalog


if __name__ == "__main__":
    catalog = refresh_catalog()
    protected = sum(record["manuallyEnriched"] for record in catalog["records"])
    print(f"Saved {len(catalog['records'])} retirement announcements ({protected} manually enriched records preserved).")
