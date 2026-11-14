"""Incremental retirement stages backed by five Git-versioned SQLite stores."""

import argparse
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import sqlite3
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urldefrag, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import html5lib

from .catalog import ROOT, parse_catalog
from .feed import ENDPOINT, normalize, title_date
from .manual_data import IDENTITY_FIELDS, MANUAL_SCHEMA, compose_catalog, merge_fields
from .refresh_data import read_snapshot, write_snapshot
from .review_data import review_snapshot

EXTRACTOR_VERSION = 1
MAX_BYTES = 8 * 1024 * 1024
HOSTS = {
    "www.microsoft.com", "azure.microsoft.com", "learn.microsoft.com",
    "techcommunity.microsoft.com", "aka.ms", "go.microsoft.com",
}
SCHEMAS = {
    "manual": MANUAL_SCHEMA,
    "raw": """
        CREATE TABLE documents (
            source TEXT, source_key TEXT, url TEXT NOT NULL, sha256 TEXT NOT NULL,
            body BLOB NOT NULL, PRIMARY KEY (source, source_key));
        CREATE TABLE targets (
            retirement_id TEXT, source TEXT, source_key TEXT,
            PRIMARY KEY (retirement_id, source),
            FOREIGN KEY (source, source_key) REFERENCES documents(source, source_key));
    """,
    "extracted": """
        CREATE TABLE observations (
            retirement_id TEXT, source TEXT, source_key TEXT, input_sha256 TEXT NOT NULL,
            extractor_version INTEGER NOT NULL, observation_json TEXT NOT NULL,
            PRIMARY KEY (retirement_id, source));
    """,
    "web_cache": """
        CREATE TABLE pages (
            url TEXT PRIMARY KEY, resolved_url TEXT, sha256 TEXT, body BLOB,
            etag TEXT, last_modified TEXT, content_type TEXT, fetched_at TEXT, error TEXT);
        CREATE TABLE record_links (
            retirement_id TEXT, url TEXT, role TEXT, cache_key TEXT, skipped_reason TEXT,
            PRIMARY KEY (retirement_id, url, role));
    """,
    "canonical": """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE retirements (
            id TEXT PRIMARY KEY, position INTEGER NOT NULL UNIQUE, record_json TEXT NOT NULL,
            input_sha256 TEXT, approved_sha256 TEXT);
        CREATE TABLE provenance (
            retirement_id TEXT PRIMARY KEY REFERENCES retirements(id), inputs_json TEXT NOT NULL);
        CREATE VIEW canonical_view AS
            SELECT r.*, p.inputs_json FROM retirements r
            LEFT JOIN provenance p ON p.retirement_id = r.id;
    """,
}


def digest(body):
    return hashlib.sha256(body).hexdigest()


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def fingerprint(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def catalog_bytes(catalog):
    return (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode()


def public_url(url, resolve=False):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password
            or parsed.port not in (None, 443)):
        raise ValueError(f"Not an approved public HTTPS endpoint: {url}")
    if resolve:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError(f"Private or unresolved destination: {url}")
    return urldefrag(url)[0]


class PublicRedirects(HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 2

    def redirect_request(self, request, response, code, message, headers, new_url):
        public_url(new_url, resolve=True)
        return super().redirect_request(request, response, code, message, headers, new_url)


def open_public(request):
    public_url(request.full_url, resolve=True)
    return build_opener(ProxyHandler({}), PublicRedirects()).open(request, timeout=60)


def retry_delay(error, attempt):
    value = error.headers.get("Retry-After") if isinstance(error, HTTPError) and error.headers else None
    if value:
        try:
            delay = float(value)
        except ValueError:
            delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        if delay > 60:
            raise ValueError("Retry-After exceeds this bounded run; retry the stage later") from error
        return max(0, delay)
    return 2 ** attempt


def put(connection, table, keys, values):
    where = " AND ".join(f"{key}=?" for key in keys)
    previous = connection.execute(
        f"SELECT * FROM {table} WHERE {where}", [values[key] for key in keys],
    ).fetchone()
    if previous is not None and dict(previous) == values:
        return False
    columns = ",".join(values)
    updates = ",".join(f"{key}=excluded.{key}" for key in values if key not in keys)
    connection.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in values)}) "
        f"ON CONFLICT ({','.join(keys)}) DO UPDATE SET {updates}", list(values.values()),
    )
    return True


def announcement_id(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "azure.microsoft.com":
        raise ValueError("The target needs its original Azure Updates announcement identity")
    path = re.sub(r"^/[a-z]{2}-[a-z]{2}(?=/)", "", parsed.path).strip("/")
    if path == "updates":
        values = parse_qs(parsed.query).get("id", [])
        if len(values) == 1 and values[0]:
            return values[0]
    parts = path.split("/")
    if len(parts) == 2 and parts[0] == "updates":
        return parts[1]
    raise ValueError("Unsupported Azure Updates announcement URL")


def lifecycle_observation(body, identifier):
    document = html5lib.parse(body, namespaceHTMLElements=False)
    matches = []
    section = None
    for node in document.iter():
        if node.tag == "h2":
            section = " ".join("".join(node.itertext()).split())
        if node.tag != "tr" or section != "Additional Azure Changes":
            continue
        cells = node.findall("td")
        if len(cells) != 2:
            continue
        for anchor in cells[0].iter("a"):
            reference = anchor.get("href", "")
            try:
                matching = announcement_id(reference) == identifier
            except ValueError:
                matching = False
            if matching:
                raw_date = " ".join("".join(cells[1].itertext()).split())
                matches.append({
                    "title": " ".join("".join(anchor.itertext()).split()),
                    "referenceUrl": reference, "section": section, "rawDate": raw_date,
                    "provisionalDate": title_date("Retires on " + raw_date),
                    "identityEvidence": "Explicit cross-reference to the exact Azure Updates item; no neighbor scope inherited.",
                })
    if len(matches) != 1 or not matches[0]["title"]:
        raise ValueError("Expected exactly one explicitly linked Lifecycle entry; do not infer identity from dates")
    return matches[0]


class Pipeline:
    def __init__(self, directory=ROOT / "data" / "pipeline", output=ROOT / "data" / "retirements.json"):
        self.directory, self.output = Path(directory), Path(output)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = self.directory / ".lock"
        self.connections = {}
        descriptor = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(str(os.getpid()))
            if (self.directory / "links.sqlite").exists():
                raise ValueError(
                    "Legacy links.sqlite found: close all database connections and rename it to web_cache.sqlite. "
                    "If both files exist, reconcile them without overwriting either cache."
                )
            if not (self.directory / "manual.sqlite").exists():
                snapshot = read_snapshot(self.output)
                catalog = json.loads(snapshot) if snapshot is not None else {}
                if isinstance(catalog, dict) and isinstance(catalog.get("records"), list) and any(
                    isinstance(record, dict) and "manualEnrichment" in record
                    for record in catalog.get("records", [])
                ):
                    raise ValueError("Missing manual.sqlite for composed content; restore the manual database")
            for name, schema in SCHEMAS.items():
                connection = sqlite3.connect(self.directory / f"{name}.sqlite")
                self.connections[name] = connection
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=DELETE")
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    connection.executescript("BEGIN;" + schema + "PRAGMA user_version=1; COMMIT;")
                elif version != 1:
                    raise ValueError(f"Unsupported {name} database schema: {version}")
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        for connection in self.connections.values():
            connection.close()
        self.connections.clear()
        self.lock.unlink(missing_ok=True)

    def metadata(self, key):
        row = self.connections["canonical"].execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        if row is None:
            raise ValueError("Seed the canonical baseline first")
        return row[0]

    def seed(self):
        raw = self.output.read_bytes()
        catalog = json.loads(raw)
        parse_catalog(catalog)
        connection = self.connections["canonical"]
        if connection.execute("SELECT COUNT(*) FROM retirements").fetchone()[0]:
            if self.metadata("export_sha256") != digest(raw):
                raise ValueError("Existing JSON changed outside the pipeline; reconcile it before reseeding/export")
            return {"seeded": 0, "unchanged": len(catalog["records"])}
        if any("manualEnrichment" in record for record in catalog["records"]):
            raise ValueError("Cannot seed automatic research from composed manual content; preserve the existing databases")
        with connection:
            connection.executemany("INSERT INTO metadata VALUES (?,?)", [
                ("catalog", packed({key: value for key, value in catalog.items() if key != "records"})),
                ("export_sha256", digest(raw)),
            ])
            connection.executemany("INSERT INTO retirements VALUES (?,?,?,NULL,NULL)", [
                (record["id"], index, packed(record)) for index, record in enumerate(catalog["records"])
            ])
        return {"seeded": len(catalog["records"])}

    def row(self, identifier):
        row = self.connections["canonical"].execute("SELECT * FROM retirements WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown retirement {identifier}; seed the baseline first")
        return dict(row)

    def page(self, url):
        row = self.connections["web_cache"].execute("SELECT * FROM pages WHERE url=?", (urldefrag(url)[0],)).fetchone()
        return dict(row) if row is not None else None

    def download(self, url):
        key = public_url(url)
        old = self.page(key)
        headers = {"Accept-Encoding": "identity", "User-Agent": "Azure-Retirements-Pipeline/1.0"}
        if old and old["etag"]:
            headers["If-None-Match"] = old["etag"]
        elif old and old["last_modified"]:
            headers["If-Modified-Since"] = old["last_modified"]
        try:
            for attempt in range(5):
                try:
                    with open_public(Request(key, headers=headers)) as response:
                        if response.status != 200:
                            raise ValueError(f"Expected a complete HTTP 200 response, got {response.status}")
                        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                            raise ValueError("Unsupported response encoding despite Accept-Encoding: identity")
                        body = response.read(MAX_BYTES + 1)
                        if len(body) > MAX_BYTES:
                            raise ValueError(f"Response exceeds {MAX_BYTES} bytes")
                        length = response.headers.get("Content-Length")
                        if length is not None and len(body) != int(length):
                            raise ValueError("Incomplete HTTP response; cached body preserved")
                        resolved = public_url(response.geturl())
                        values = {
                            "url": key, "resolved_url": resolved, "sha256": digest(body), "body": body,
                            "etag": response.headers.get("ETag"),
                            "last_modified": response.headers.get("Last-Modified"),
                            "content_type": response.headers.get("Content-Type"), "fetched_at": None, "error": None,
                        }
                    same = old and all(old[field] == value for field, value in values.items() if field != "fetched_at")
                    values["fetched_at"] = old["fetched_at"] if same else datetime.now(timezone.utc).isoformat()
                    with self.connections["web_cache"]:
                        changed = put(self.connections["web_cache"], "pages", ("url",), values)
                    return {"url": key, "outcome": "downloaded" if not old or old["sha256"] != values["sha256"] else "identical",
                            "databaseChanged": changed, "validator": bool(values["etag"] or values["last_modified"])}
                except HTTPError as error:
                    if error.code == 304:
                        if not old or old["body"] is None or not any(name in headers for name in ("If-None-Match", "If-Modified-Since")):
                            raise ValueError("Unexpected 304 without a validated cached body") from error
                        if public_url(error.geturl()) != old["resolved_url"]:
                            headers.pop("If-None-Match", None)
                            headers.pop("If-Modified-Since", None)
                            if attempt == 4:
                                raise ValueError("Redirect destination changed; retry without old validators") from error
                            continue
                        if old["error"]:
                            with self.connections["web_cache"]:
                                put(self.connections["web_cache"], "pages", ("url",), {**old, "error": None})
                        return {"url": key, "outcome": "not-modified", "databaseChanged": bool(old["error"]), "validator": True}
                    if attempt == 4 or error.code not in (408, 429) and error.code < 500:
                        raise
                    time.sleep(retry_delay(error, attempt))
                except (URLError, TimeoutError, http.client.HTTPException) as error:
                    if attempt == 4:
                        raise
                    time.sleep(retry_delay(error, attempt))
        except (HTTPError, URLError, TimeoutError, ValueError, OSError, http.client.HTTPException) as error:
            values = old or {field: None for field in (
                "resolved_url", "sha256", "body", "etag", "last_modified", "content_type", "fetched_at",
            )}
            values = {**values, "url": key, "error": f"{type(error).__name__}: {error}"}
            with self.connections["web_cache"]:
                put(self.connections["web_cache"], "pages", ("url",), values)
            raise

    def ingest(self, identifier, lifecycle_url):
        record = json.loads(self.row(identifier)["record_json"])
        if record.get("hidden", False):
            raise ValueError("Hidden records are not pipeline content targets")
        source_id = announcement_id(record["sourceUrl"])
        parsed = urlsplit(public_url(lifecycle_url))
        if parsed.hostname != "learn.microsoft.com" or not re.fullmatch(
            r"/(?:[a-z]{2}-[a-z]{2}/)?lifecycle/end-of-support/end-of-support-\d{4}/?", parsed.path,
        ):
            raise ValueError("Use the applicable Microsoft Lifecycle annual index")
        api = ENDPOINT + "?" + urlencode({
            "$filter": "id eq '" + source_id.replace("'", "''") + "'", "$top": "2", "$count": "true",
        })
        results = [self.download(url) for url in (api, lifecycle_url)]
        pages = [self.page(url) for url in (api, lifecycle_url)]
        data = json.loads(pages[0]["body"])
        if (data.get("@odata.count") != 1 or len(data.get("value", [])) != 1
                or str(data["value"][0].get("id")) != source_id):
            raise ValueError("Azure Updates did not return exactly the selected source item")
        normalize(data["value"][0])
        lifecycle_observation(pages[1]["body"], source_id)
        changed = 0
        with self.connections["raw"]:
            for source, key, page in zip(("azure-updates", "lifecycle"), (source_id, lifecycle_url), pages):
                changed += put(self.connections["raw"], "documents", ("source", "source_key"), {
                    "source": source, "source_key": key, "url": page["url"], "sha256": page["sha256"], "body": page["body"],
                })
                put(self.connections["raw"], "targets", ("retirement_id", "source"), {
                    "retirement_id": identifier, "source": source, "source_key": key,
                })
        return {"changedDocuments": changed, "requests": results}

    def documents(self, identifier):
        rows = self.connections["raw"].execute(
            "SELECT d.* FROM documents d JOIN targets t USING(source,source_key) "
            "WHERE retirement_id=? ORDER BY source", (identifier,),
        ).fetchall()
        if {row["source"] for row in rows} != {"azure-updates", "lifecycle"}:
            raise ValueError("Ingest both selected discovery sources first")
        return [dict(row) for row in rows]

    def extract(self, identifier):
        documents = self.documents(identifier)
        source_id = next(row["source_key"] for row in documents if row["source"] == "azure-updates")
        changed = 0
        proposals = []
        for document in documents:
            old = self.connections["extracted"].execute(
                "SELECT * FROM observations WHERE retirement_id=? AND source=?", (identifier, document["source"]),
            ).fetchone()
            if (old and old["input_sha256"] == document["sha256"] and old["extractor_version"] == EXTRACTOR_VERSION
                    and old["source_key"] == document["source_key"]):
                continue
            if document["source"] == "azure-updates":
                record = normalize(json.loads(document["body"])["value"][0])
                observation = {key: record[key] for key in (
                    "id", "title", "sourceUrl", "services", "categories", "announcedOn", "lastUpdatedOn",
                )}
                observation.update({
                    "announcement": record["questions"]["what"]["announcement"],
                    "resources": record["questions"]["actions"]["resources"],
                    "provisionalDeadline": {key: record["questions"]["deadline"][key] for key in ("date", "month")},
                })
            else:
                observation = lifecycle_observation(document["body"], source_id)
            proposals.append({
                "retirement_id": identifier, "source": document["source"], "source_key": document["source_key"],
                "input_sha256": document["sha256"], "extractor_version": EXTRACTOR_VERSION,
                "observation_json": packed(observation),
            })
        with self.connections["extracted"]:
            for proposal in proposals:
                changed += put(self.connections["extracted"], "observations", ("retirement_id", "source"), proposal)
        return {"extracted": changed, "unchanged": len(documents) - changed}

    def references(self, identifier):
        record = json.loads(self.row(identifier)["record_json"])
        values = {(record["sourceUrl"], "announcement")}
        values.update((resource["url"], "resource") for resource in record["questions"]["actions"]["resources"])
        values.update((source["url"], "citation") for source in record.get("sourceReview", {}).get("sources", []))
        values.add((record["questions"]["actions"]["support"]["url"], "support"))
        values.add((record["questions"]["impact"]["advisor"]["url"], "advisor"))
        values.update((document["url"], "discovery") for document in self.documents(identifier))
        return sorted(values)

    def links(self, identifier):
        record = json.loads(self.row(identifier)["record_json"])
        review = record.get("sourceReview", {})
        checks = {check["url"]: check for check in review.get("resourceChecks", [])}
        required = {record["sourceUrl"]} | {source["url"] for source in review.get("sources", [])}
        references = []
        for url, role in self.references(identifier):
            reason = None
            if role in ("support", "advisor") or urlsplit(url).hostname == "portal.azure.com":
                reason = "Support/Advisor or authenticated portal; not downloaded and not product evidence."
            elif urlsplit(url).hostname == "ms.portal.azure.com":
                reason = "Authenticated support portal; not downloaded and not product evidence."
            elif role == "resource" and url not in required and checks.get(url, {}).get("status") in (
                "not-evidence", "unavailable",
            ):
                check = checks[url]
                reason = f"Optional reference classified {check['status']}: {check['detail']}"
            if reason and url in required:
                raise ValueError(f"Required citation cannot be classified as a skipped reference: {url}")
            if reason is None:
                public_url(url)
            references.append({
                "retirement_id": identifier, "url": url, "role": role,
                "cache_key": urldefrag(url)[0] if reason is None else None, "skipped_reason": reason,
            })
        connection = self.connections["web_cache"]
        old = [dict(row) for row in connection.execute(
            "SELECT * FROM record_links WHERE retirement_id=? ORDER BY url,role", (identifier,),
        )]
        if old != references:
            with connection:
                connection.execute("DELETE FROM record_links WHERE retirement_id=?", (identifier,))
                connection.executemany("INSERT INTO record_links VALUES (?,?,?,?,?)", [
                    tuple(reference.values()) for reference in references
                ])
        results, errors = [], []
        source_urls = {document["url"] for document in self.documents(identifier)}
        for url in sorted({reference["cache_key"] for reference in references if reference["cache_key"]}):
            if url in source_urls:
                page = self.page(url)
                if page and not page["error"] and page["body"] is not None:
                    results.append({"url": url, "outcome": "reused-source", "databaseChanged": False,
                                    "validator": bool(page["etag"] or page["last_modified"])})
                    continue
            try:
                results.append(self.download(url))
            except (HTTPError, URLError, TimeoutError, ValueError, OSError, http.client.HTTPException) as error:
                errors.append({"url": url, "error": str(error)})
        if errors:
            raise ValueError("Link refresh failed; cached bodies retained, promotion blocked: " + packed(errors))
        return {"references": len(references), "skipped": sum(bool(r["skipped_reason"]) for r in references), "requests": results}

    def inputs(self, identifier):
        observations = []
        for document in self.documents(identifier):
            page = self.page(document["url"])
            if not page or page["error"] or page["sha256"] != document["sha256"]:
                raise ValueError("Raw source cache changed/failed; rerun ingest and extract")
            row = self.connections["extracted"].execute(
                "SELECT * FROM observations WHERE retirement_id=? AND source=?", (identifier, document["source"]),
            ).fetchone()
            if (not row or row["input_sha256"] != document["sha256"]
                    or row["extractor_version"] != EXTRACTOR_VERSION or row["source_key"] != document["source_key"]):
                raise ValueError("Missing or stale extracted input; rerun extract")
            observations.append(dict(row))
        links = [dict(row) for row in self.connections["web_cache"].execute(
            "SELECT * FROM record_links WHERE retirement_id=? ORDER BY url,role", (identifier,),
        )]
        if {(row["url"], row["role"]) for row in links} != set(self.references(identifier)):
            raise ValueError("Missing or stale link references; rerun links")
        for link in links:
            if link["cache_key"]:
                page = self.page(link["cache_key"])
                if not page or page["error"] or page["body"] is None:
                    raise ValueError(f"Missing/failed link check: {link['url']}")
                link.update({"bodySha256": page["sha256"], "resolvedUrl": page["resolved_url"]})
        return {"observations": observations, "links": links}

    def canonical(self, identifier, accept_review=False, input_sha256=None, record_sha256=None):
        inputs = self.inputs(identifier)
        sha = fingerprint(inputs)
        row = self.row(identifier)
        record = json.loads(row["record_json"])
        if record.get("hidden", False):
            raise ValueError("Hidden records cannot be promoted by automatic assembly")
        if accept_review and record.get("sourceReview", {}).get("status") != "enriched":
            raise ValueError("Accept only an evidence-reviewed five-question record")
        if accept_review and (input_sha256 != sha or record_sha256 != fingerprint(record)):
            raise ValueError("Review fingerprints changed or were not supplied; inspect canonical output before approving")
        row["input_sha256"] = sha
        if accept_review:
            row["approved_sha256"] = sha
        with self.connections["canonical"]:
            changed = put(self.connections["canonical"], "retirements", ("id",), row)
            put(self.connections["canonical"], "provenance", ("retirement_id",), {
                "retirement_id": identifier, "inputs_json": packed(inputs),
            })
        return {"id": identifier, "inputSha256": sha, "recordSha256": fingerprint(record),
                "changed": changed, "reviewRequired": row["approved_sha256"] != sha}

    def catalog(self, automatic=False):
        catalog = json.loads(self.metadata("catalog"))
        catalog["records"] = [json.loads(row[0]) for row in self.connections["canonical"].execute(
            "SELECT record_json FROM retirements ORDER BY position",
        )]
        parse_catalog(catalog)
        return catalog if automatic else compose_catalog(catalog, self.manual_rows())

    def manual_rows(self):
        return [dict(row) for row in self.connections["manual"].execute(
            "SELECT * FROM overrides ORDER BY retirement_id",
        )]

    def manual(self, batch):
        if not isinstance(batch, dict) or batch.get("catalogSha256") != digest(catalog_bytes(self.catalog())):
            raise ValueError("Catalog changed since manual preparation; existing manual content preserved")
        updates = batch.get("overrides")
        if not isinstance(updates, list) or not updates:
            raise ValueError("A nonempty manual override batch is required")
        rows = {row["retirement_id"]: row for row in self.manual_rows()}
        seen = set()
        for update in updates:
            if not isinstance(update, dict) or set(update) != {"id", "fields"}:
                raise ValueError("Manual updates require exactly id and fields")
            identifier = update["id"]
            if not isinstance(identifier, str) or identifier in seen:
                raise ValueError("Invalid or duplicate manual retirement ID")
            seen.add(identifier)
            existing = rows.get(identifier)
            if update["fields"] is None:
                if existing is None:
                    raise ValueError(f"No manual content to remove for {identifier}")
                del rows[identifier]
                continue
            if not isinstance(update["fields"], dict) or not update["fields"]:
                raise ValueError("Manual fields must be a nonempty object, or null to remove an override")
            base = existing["base_record_json"] if existing else self.row(identifier)["record_json"]
            current = self.connections["canonical"].execute(
                "SELECT record_json FROM retirements WHERE id=?", (identifier,),
            ).fetchone()
            if json.loads(current[0] if current else base).get("hidden", False):
                raise ValueError("Hidden records cannot receive manual content")
            fields = merge_fields(json.loads(existing["fields_json"]) if existing else {}, update["fields"])
            questions = update["fields"].get("questions", {})
            if isinstance(questions, dict):
                for section, changes in questions.items():
                    if isinstance(changes, dict) and changes and "html" not in changes:
                        fields["questions"][section].pop("html", None)
            rows[identifier] = {
                "retirement_id": identifier, "fields_json": packed(fields), "base_record_json": base,
            }
        compose_catalog(self.catalog(automatic=True), rows.values())
        changed = 0
        connection = self.connections["manual"]
        with connection:
            for identifier in seen:
                if identifier in rows:
                    changed += put(connection, "overrides", ("retirement_id",), rows[identifier])
                else:
                    changed += connection.execute(
                        "DELETE FROM overrides WHERE retirement_id=?", (identifier,),
                    ).rowcount
        return {"changed": changed, "manualRecords": len(rows), "next": "export, then rebuild the site"}

    def migrate(self):
        original = self.output.read_bytes()
        if digest(original) != self.metadata("export_sha256"):
            raise ValueError("JSON changed outside the canonical database; reconcile before migration")
        records, overrides = [], {row["retirement_id"]: row for row in self.manual_rows()}
        for row in self.connections["canonical"].execute("SELECT * FROM retirements ORDER BY position"):
            record = json.loads(row["record_json"])
            if "manuallyEnriched" not in record:
                continue
            flag = record.pop("manuallyEnriched")
            if type(flag) is not bool:
                raise ValueError("Invalid legacy manual flag; migration preserved existing data")
            if flag:
                fields = {key: value for key, value in record.items() if key not in IDENTITY_FIELDS}
                fields["questions"] = {
                    section: {key: value for key, value in answer.items() if key != "question"}
                    for section, answer in fields["questions"].items()
                }
                previous = overrides.get(record["id"])
                overrides[record["id"]] = {
                    "retirement_id": record["id"], "base_record_json": packed(record),
                    "fields_json": packed(merge_fields(fields, json.loads(previous["fields_json"]) if previous else {})),
                }
            records.append({**dict(row), "record_json": packed(record)})
        proposed = json.loads(self.metadata("catalog"))
        changes = {row["id"]: row["record_json"] for row in records}
        proposed["records"] = [json.loads(changes.get(row["id"], row["record_json"]))
                               for row in self.connections["canonical"].execute("SELECT * FROM retirements ORDER BY position")]
        compose_catalog(proposed, overrides.values())
        with self.connections["manual"]:
            for row in overrides.values():
                put(self.connections["manual"], "overrides", ("retirement_id",), row)
        with self.connections["canonical"]:
            for row in records:
                put(self.connections["canonical"], "retirements", ("id",), row)
        return {"migratedRecords": len(records), "manualRecords": len(overrides), "export": self.export()}

    def review(self, batch):
        original = self.catalog(automatic=True)
        reviewed = review_snapshot(batch, catalog_bytes(original))
        changed = []
        connection = self.connections["canonical"]
        with connection:
            for update in batch["reviews"]:
                identifier = update["id"]
                row = self.row(identifier)
                previous = json.loads(row["record_json"])
                record = next(record for record in reviewed["records"] if record["id"] == identifier)
                if previous.get("hidden", False):
                    raise ValueError("Hidden records must remain unchanged")
                row.update({"record_json": packed(record), "approved_sha256": None})
                put(connection, "retirements", ("id",), row)
                changed.append(identifier)
        return {"reviewed": changed, "next": "Refresh links if references changed, then canonical --accept-review and export"}

    def export(self):
        for target in self.connections["raw"].execute("SELECT DISTINCT retirement_id FROM targets"):
            if self.row(target[0])["input_sha256"] is None:
                raise ValueError(f"Missing canonical assembly for {target[0]}")
        for row in self.connections["canonical"].execute("SELECT * FROM retirements WHERE input_sha256 IS NOT NULL"):
            if row["approved_sha256"] != row["input_sha256"] or fingerprint(self.inputs(row["id"])) != row["input_sha256"]:
                raise ValueError(f"Stale or unapproved canonical inputs for {row['id']}; review and reassemble before export")
        catalog = self.catalog()
        original = read_snapshot(self.output)
        if original is not None and json.loads(original) == catalog:
            with self.connections["canonical"]:
                put(self.connections["canonical"], "metadata", ("key",), {
                    "key": "export_sha256", "value": digest(original),
                })
            return {"changed": False, "records": len(catalog["records"]), "catalogSha256": digest(original)}
        if original is not None and digest(original) != self.metadata("export_sha256"):
            raise ValueError("JSON changed outside the canonical database; existing output preserved")
        write_snapshot(catalog, self.output, original, operation="database export")
        sha = digest(self.output.read_bytes())
        with self.connections["canonical"]:
            put(self.connections["canonical"], "metadata", ("key",), {"key": "export_sha256", "value": sha})
        return {"changed": True, "records": len(catalog["records"]), "catalogSha256": sha}

    def status(self):
        targets = []
        for row in self.connections["canonical"].execute(
            "SELECT id,input_sha256,approved_sha256 FROM retirements WHERE input_sha256 IS NOT NULL ORDER BY position",
        ):
            target = dict(row)
            try:
                target["currentInputSha256"] = fingerprint(self.inputs(row["id"]))
                target["reviewRequired"] = target["currentInputSha256"] != row["approved_sha256"]
            except ValueError as error:
                target.update({"reviewRequired": True, "blockedReason": str(error)})
            targets.append(target)
        return {
            "databases": {name: str(self.directory / f"{name}.sqlite") for name in SCHEMAS},
            "records": self.connections["canonical"].execute("SELECT COUNT(*) FROM retirements").fetchone()[0],
            "catalogSha256": digest(catalog_bytes(self.catalog())),
            "automaticCatalogSha256": digest(catalog_bytes(self.catalog(automatic=True))),
            "manualRecords": len(self.manual_rows()),
            "rawDocuments": self.connections["raw"].execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "extractedObservations": self.connections["extracted"].execute("SELECT COUNT(*) FROM observations").fetchone()[0],
            "cachedPages": self.connections["web_cache"].execute("SELECT COUNT(*) FROM pages WHERE body IS NOT NULL").fetchone()[0],
            "linkReferences": self.connections["web_cache"].execute("SELECT COUNT(*) FROM record_links").fetchone()[0],
            "targets": targets,
            "failedLinks": [dict(row) for row in self.connections["web_cache"].execute(
                "SELECT url,error FROM pages WHERE error IS NOT NULL ORDER BY url",
            )],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dir", type=Path, default=ROOT / "data" / "pipeline")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "retirements.json")
    commands = parser.add_subparsers(dest="stage", required=True)
    for name in ("seed", "export", "status", "migrate"):
        commands.add_parser(name)
    for name in ("ingest", "extract", "links", "canonical"):
        command = commands.add_parser(name)
        command.add_argument("--id", required=True)
        if name == "ingest":
            command.add_argument("--lifecycle-url", required=True)
        if name == "canonical":
            command.add_argument("--accept-review", action="store_true", help="Explicitly attest review of the current record and exact inputs")
            command.add_argument("--input-sha256")
            command.add_argument("--record-sha256")
    commands.add_parser("review").add_argument("--batch", required=True, type=Path)
    commands.add_parser("manual").add_argument("--batch", required=True, type=Path)
    args = parser.parse_args()
    with Pipeline(args.db_dir, args.output) as pipeline:
        if args.stage == "ingest":
            result = pipeline.ingest(args.id, args.lifecycle_url)
        elif args.stage == "canonical":
            result = pipeline.canonical(args.id, args.accept_review, args.input_sha256, args.record_sha256)
        elif args.stage in ("review", "manual"):
            result = getattr(pipeline, args.stage)(json.loads(args.batch.read_text(encoding="utf-8")))
        elif args.stage in ("extract", "links"):
            result = getattr(pipeline, args.stage)(args.id)
        else:
            result = getattr(pipeline, args.stage)()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
