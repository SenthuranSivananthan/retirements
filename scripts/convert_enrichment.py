"""Read existing SQLite stores without modifying them; publish an isolated JSON conversion."""

import argparse
import copy
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

from .catalog import QUESTIONS, ROOT, parse_catalog
from .enrichment import (
    CANONICAL, ENRICH_AUTO, ENRICH_MANUAL, SOURCE_AUTO, SOURCE_MANUAL,
    Enrichment, canonical_projection, source_records,
)
from .enrichment_http import extract_html
from .enrichment_json import Stages, fingerprint, read_bytes, write_json
from .manual_data import compose_catalog
from .pipeline import announcement_id

DATABASES = ("raw", "extracted", "web_cache", "canonical", "manual")
KNOWN_TABLES = {
    "raw": {"documents", "targets"}, "extracted": {"observations"},
    "web_cache": {"pages", "record_links"}, "canonical": {"metadata", "retirements", "provenance"},
    "manual": {"overrides"},
}


def file_hash(path):
    import hashlib
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for part in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def compact_metadata(value):
    """Keep provenance identifiers/hashes, not embedded copies of source bodies."""
    if isinstance(value, dict):
        return {
            key: compact_metadata(item) for key, item in value.items()
            if key.lower().replace("_", "") not in {
                "body", "bodybase64", "bodyb64", "contentbase64", "rawbody", "html", "markdown",
            }
        }
    if isinstance(value, list):
        return [compact_metadata(item) for item in value]
    return value


def imported_summary(record):
    fields = {
        "what": ("announcement", "financialConsiderations"),
        "actions": ("recommendedAction", "guidance", "supportGuidance"),
        "impact": ("guidance", "notice"),
        "deadline": ("dateGuidance", "consequences"),
        "progress": ("guidance", "storageNote"),
    }
    answers = {}
    for key in QUESTIONS:
        question = record["questions"][key]
        if question.get("html"):
            _, text, _ = extract_html(question["html"].encode(), record["sourceUrl"])
        else:
            text = "\n\n".join(dict.fromkeys(
                question[field] for field in fields[key] if question.get(field)
            ))
        answers[key] = text or "No summary was present in the imported record."
    return {
        "summary": record["summary"], "questions": answers,
        "deadline": {key: record["questions"]["deadline"][key] for key in ("date", "month")},
    }


def cache_page(row):
    return {
        "url": row["url"], "fetchUrl": row["url"], "resolvedUrl": row["resolved_url"],
        "method": "imported-http", "representation": "imported-http",
        "httpSha256": row["sha256"], "contentSha256": None,
        "etag": row["etag"], "lastModified": row["last_modified"],
        "fetchedAt": row["fetched_at"], "checkedAt": None, "references": [], "title": "",
        "status": "failed" if row["error"] else "imported", "error": row["error"],
        "downloadedBodyBytes": row["body_bytes"],
    }


def snapshot_stores(directory, stack):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"SQLite database directory does not exist: {directory}")
    # Some writers use an existence lock rather than an OS lease. Refuse
    # either live or stale markers instead of guessing that conversion is safe.
    if (directory / ".lock").exists():
        raise ValueError("SQLite .lock exists; drain the writer and resolve its lease before conversion")
    paths = {name: directory / f"{name}.sqlite" for name in DATABASES}
    for path in paths.values():
        if not path.is_file():
            raise ValueError(f"Missing SQLite store: {path.name}")
        if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-journal")):
            raise ValueError(f"Close/checkpoint all SQLite writers before converting {path.name}")
    before = {name: file_hash(path) for name, path in paths.items()}
    connections = {}
    for name, path in paths.items():
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.25)
        stack.callback(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA busy_timeout=250")
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError(f"Unsupported SQLite schema version in {path.name}")
        connection.execute("BEGIN")
        if connection.execute("PRAGMA quick_check").fetchall()[0][0] != "ok":
            raise ValueError(f"SQLite store failed quick_check: {path.name}")
        connections[name] = connection
    return connections, paths, before


def convert(db_dir, destination, catalog_path=None, dry_run=False, allow_unmapped=False):
    """Produce JSON stage files and website projection without modifying SQLite."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Conversion destination already exists; choose a new directory (nothing is overwritten)")
    with ExitStack() as stack:
        connections, paths, before = snapshot_stores(db_dir, stack)
        unmapped = {}
        for name, connection in connections.items():
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                table = row[0]
                if table not in KNOWN_TABLES[name] and not table.startswith("sqlite_"):
                    quoted = '"' + table.replace('"', '""') + '"'
                    count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                    if count:
                        unmapped[f"{name}.{table}"] = count
        if unmapped and not (dry_run or allow_unmapped):
            raise ValueError(
                f"Unmapped auxiliary tables: {unmapped}. Inspect --dry-run; --allow-unmapped explicitly "
                "leaves these tables only in the retained SQLite stores, not the JSON conversion."
            )
        canonical = connections["canonical"]
        row = canonical.execute("SELECT value FROM metadata WHERE key='catalog'").fetchone()
        if row is None:
            raise ValueError("Canonical store is not seeded")
        automatic_catalog = json.loads(row[0])
        canonical_rows = [dict(row) for row in canonical.execute(
            "SELECT id,record_json,input_sha256,approved_sha256 FROM retirements ORDER BY position",
        )]
        automatic_catalog["records"] = [json.loads(row["record_json"]) for row in canonical_rows]
        if any(row["id"] != record.get("id") for row, record in zip(canonical_rows, automatic_catalog["records"])):
            raise ValueError("Canonical row and JSON retirement IDs disagree")
        parse_catalog(automatic_catalog)
        overrides = [dict(row) for row in connections["manual"].execute(
            "SELECT retirement_id,fields_json,base_record_json FROM overrides ORDER BY retirement_id",
        )]
        composed = compose_catalog(automatic_catalog, overrides)
        baseline_bytes = read_bytes(catalog_path) if catalog_path is not None else None
        if catalog_path is not None:
            if baseline_bytes is None or parse_catalog(json.loads(baseline_bytes)) != parse_catalog(composed):
                raise ValueError("Website catalog differs from the composed SQLite stores; reconcile before converting")
        automatic_records = {record["id"]: record for record in automatic_catalog["records"]}
        for override in overrides:
            identifier = override["retirement_id"]
            if identifier not in automatic_records:
                automatic_records[identifier] = json.loads(override["base_record_json"])
        raw_documents = [dict(row) for row in connections["raw"].execute(
            "SELECT source,source_key,url,sha256,length(body) AS body_bytes FROM documents ORDER BY source,source_key",
        )]
        raw_targets = [dict(row) for row in connections["raw"].execute(
            "SELECT retirement_id,source,source_key FROM targets ORDER BY retirement_id,source",
        )]
        observations = [dict(row) for row in connections["extracted"].execute(
            "SELECT retirement_id,source,source_key,input_sha256,extractor_version "
            "FROM observations ORDER BY retirement_id,source",
        )]
        cache = {row["url"]: cache_page(dict(row)) for row in connections["web_cache"].execute(
            "SELECT url,resolved_url,sha256,etag,last_modified,fetched_at,error,length(body) AS body_bytes "
            "FROM pages ORDER BY url",
        )}
        links = [dict(row) for row in connections["web_cache"].execute(
            "SELECT retirement_id,url,role,cache_key,skipped_reason FROM record_links ORDER BY retirement_id,url,role",
        )]
        provenance = {
            row["retirement_id"]: compact_metadata(json.loads(row["inputs_json"]))
            for row in canonical.execute("SELECT retirement_id,inputs_json FROM provenance")
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=destination.name + ".convert-", dir=destination.parent) as temporary:
            with Stages(temporary) as store:
                store.initialize()
                source_auto = store.load(SOURCE_AUTO)
                enrichment = store.load(ENRICH_AUTO)
                manual = store.load(ENRICH_MANUAL)
                canonical_stage = store.load(CANONICAL)
                manual["recordOverrides"] = {
                    row["retirement_id"]: json.loads(row["fields_json"]) for row in overrides
                }
                enrichment["pages"] = copy.deepcopy(cache)
                retained = []
                for identifier, record in automatic_records.items():
                    try:
                        announcement_id(record["sourceUrl"])
                    except ValueError:
                        # Do not relabel old Lifecycle/other discoveries as
                        # user-supplied manual links without that user input.
                        retained.append(identifier)
                        continue
                    source_auto["records"][identifier] = {
                        key: copy.deepcopy(record[key]) for key in
                        ("title", "services", "announcedOn", "lastUpdatedOn")
                    } | {
                        "urls": [record["sourceUrl"]], "categories": record.get("categories", ["Uncategorized"]),
                        "present": True,
                    }
                    url = record["sourceUrl"]
                    page = copy.deepcopy(cache.get(url, {
                        "url": url, "fetchUrl": url, "resolvedUrl": None, "contentSha256": None,
                        "references": [], "status": "imported", "error": None,
                        "method": "sqlite-import", "title": record["title"],
                    }))
                    source_auto["pages"][url] = page
                    enrichment["pages"].setdefault(url, copy.deepcopy(page))
                sources = source_records(store)
                engine = Enrichment(store)
                for identifier, record in automatic_records.items():
                    value = imported_summary(record)
                    source = sources.get(identifier)
                    urls = list(source["urls"]) if source else []
                    urls.extend(link["url"] for link in links
                                if link["retirement_id"] == identifier and link["url"] not in urls)
                    urls = [url for url in urls if url in enrichment["pages"]]
                    enrichment["records"][identifier] = {
                        **value, "summaryRevision": fingerprint(value), "origin": "sqlite-import",
                        "processorVersion": "sqlite-import", "inputUrls": urls, "issues": [],
                        "error": None, "importedRecord": copy.deepcopy(record),
                        "importedRecordRevision": fingerprint(record), "importedInputUrls": urls,
                        "importedSourceRevision": fingerprint({
                            url: source_auto["pages"].get(url) for url in source["urls"]
                        }) if source else None,
                        "inputRevision": engine.revision(source, enrichment, urls) if source else None,
                        "importedProvenance": provenance.get(identifier),
                    }
                enrichment["sqliteImport"] = {
                    "databaseSha256": before, "rawDocuments": raw_documents, "rawTargets": raw_targets,
                    "extractedInputs": observations, "recordLinks": links,
                    "storedApprovals": {
                        row["id"]: {"inputSha256": row["input_sha256"], "approvedSha256": row["approved_sha256"]}
                        for row in canonical_rows if row["approved_sha256"] is not None
                    },
                    "retainedOutsideDiscovery": retained,
                    "unmappedAuxiliaryTables": unmapped,
                    "note": "Downloaded data and stored approvals carried forward from SQLite without refetching.",
                }
                for name in (SOURCE_AUTO, ENRICH_AUTO, ENRICH_MANUAL):
                    store.save(name)
                canonical_stage["records"] = {
                    record["id"]: copy.deepcopy(record) for record in composed["records"]
                }
                canonical_stage["catalogMetadata"] = {
                    key: copy.deepcopy(value) for key, value in composed.items()
                    if key not in {"schemaVersion", "records"}
                }
                canonical_stage["revisions"] = {}
                for identifier, record in canonical_stage["records"].items():
                    revision = {"recordSha256": fingerprint(record)}
                    if identifier in sources:
                        revision["sourceSha256"] = fingerprint(sources[identifier])
                    imported = enrichment["records"].get(identifier)
                    if imported and imported.get("inputRevision"):
                        revision["automaticInputRevision"] = imported["inputRevision"]
                    if identifier in manual["recordOverrides"]:
                        revision["manualFieldsSha256"] = fingerprint(manual["recordOverrides"][identifier])
                    canonical_stage["revisions"][identifier] = revision
                projection = canonical_projection(canonical_stage)
                canonical_stage["projectionRevision"] = fingerprint(parse_catalog(projection))
                store.save(CANONICAL)
                write_json(Path(temporary) / "retirements.json", projection, None)
            after = {name: file_hash(path) for name, path in paths.items()}
            if before != after or (Path(db_dir) / ".lock").exists():
                raise ValueError("SQLite stores changed during conversion; staged output discarded")
            if catalog_path is not None and read_bytes(catalog_path) != baseline_bytes:
                raise ValueError("Website catalog changed during conversion; staged output discarded")
            report = {
                "dryRun": dry_run, "records": len(composed["records"]),
                "automaticSources": len(sources), "manualOverrides": len(overrides),
                "retainedOutsideDiscovery": retained, "cachedPages": len(cache),
                "storedApprovalsNotRevalidated": sum(row["approved_sha256"] is not None for row in canonical_rows),
                "unmappedAuxiliaryTables": unmapped,
                "readyToPublish": not unmapped or allow_unmapped,
                "databaseSha256": before, "destination": str(destination),
                "note": "Freshness metadata preserved; no refetch or page-body copies. Source stores unchanged.",
            }
            if not dry_run:
                if destination.exists():
                    raise ValueError("Conversion destination appeared during conversion; nothing replaced")
                # The destination must be new; publishing the directory makes
                # the complete stage set and website projection visible together.
                Path(temporary, ".enrichment-work", ".lock").unlink(missing_ok=True)
                Path(temporary, ".enrichment-work").rmdir()
                os.rename(temporary, destination)
            return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dir", type=Path, default=ROOT / "data" / "pipeline")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; existing paths are never overwritten")
    parser.add_argument("--catalog", type=Path, help="Optional current website JSON to check against composed store content")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without publishing output files")
    parser.add_argument("--allow-unmapped", action="store_true",
                        help="Explicitly leave reported auxiliary tables only in the retained SQLite databases")
    args = parser.parse_args(argv)
    try:
        report = convert(args.db_dir, args.output_dir, args.catalog, args.dry_run, args.allow_unmapped)
        print(json.dumps(report, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"Conversion failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
