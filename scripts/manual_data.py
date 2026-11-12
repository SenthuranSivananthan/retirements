"""Compose user-provided field overrides without changing automatic research."""

import copy
import json
import sqlite3
from pathlib import Path

from .catalog import QUESTIONS, parse_catalog

MANUAL_SCHEMA = """
    CREATE TABLE overrides (
        retirement_id TEXT PRIMARY KEY, fields_json TEXT NOT NULL, base_record_json TEXT NOT NULL);
"""
IDENTITY_FIELDS = frozenset((
    "id", "title", "sourceUrl", "service", "services", "categories", "announcedOn", "lastUpdatedOn",
    "hidden", "manuallyEnriched", "manualEnrichment",
))


def merge_fields(original, changes):
    result = copy.deepcopy(original)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_fields(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def field_paths(fields, prefix=""):
    paths = []
    for key, value in fields.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.extend(field_paths(value, path) if isinstance(value, dict) and value else [path])
    return sorted(paths)


def compose_catalog(catalog, overrides):
    result = copy.deepcopy(catalog)
    records = {record["id"]: record for record in result["records"]}
    for row in sorted(overrides, key=lambda row: row["retirement_id"]):
        identifier = row["retirement_id"]
        fields = json.loads(row["fields_json"])
        if not isinstance(fields, dict) or not fields or set(fields) & IDENTITY_FIELDS:
            raise ValueError(f"Invalid manual fields for {identifier}; identity/source metadata cannot be overridden")
        questions = fields.get("questions", {})
        if not isinstance(questions, dict) or set(questions) - set(QUESTIONS):
            raise ValueError(f"Invalid manual questions for {identifier}")
        if any(not isinstance(value, dict) or "question" in value for value in questions.values()):
            raise ValueError(f"Manual answers must preserve question headings for {identifier}")
        base = records.get(identifier)
        if base is None:
            base = json.loads(row["base_record_json"])
            if base.get("id") != identifier:
                raise ValueError("Manual baseline identity does not match its retirement")
        if base.get("hidden", False):
            continue
        for section, changes in questions.items():
            allowed = (set(base["questions"][section]) - {"question"}) | {"html"}
            if section == "progress":
                allowed.add("tracking")
            if set(changes) - allowed:
                raise ValueError(f"Unknown manual answer fields for {identifier}/{section}")
        record = merge_fields(base, fields)
        for section, changes in questions.items():
            if changes and "html" not in changes:
                record["questions"][section].pop("html", None)
        record["manualEnrichment"] = {"fields": field_paths(fields)}
        records[identifier] = record
    order = [record["id"] for record in result["records"]]
    order.extend(sorted(set(records) - set(order)))
    result["records"] = [records[identifier] for identifier in order]
    parse_catalog(result)
    return result


def read_overrides(path):
    path = Path(path)
    if not path.exists():
        return []
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("Unsupported manual database schema")
        return [dict(row) for row in connection.execute("SELECT * FROM overrides ORDER BY retirement_id")]
    finally:
        connection.close()
