import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fixtures import ITEM, catalog
from scripts.catalog import QUESTIONS, parse_catalog
from scripts.convert_enrichment import DATABASES, convert, file_hash
from scripts.enrichment import CANONICAL, ENRICH_AUTO, ENRICH_MANUAL, SOURCE_AUTO, Enrichment, merge
from scripts.enrichment_json import Stages, fingerprint
from scripts.pipeline import Pipeline, catalog_bytes, digest, packed
from scripts.refresh_data import refresh_catalog


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "retirements.json"
        self.db = self.root / "pipeline"
        self.destination = self.root / "converted"
        self.output.write_bytes(catalog_bytes(catalog()))
        with Pipeline(self.db, self.output) as pipeline:
            pipeline.seed()
            body = b"<main>Downloaded source bytes must not be copied.</main>"
            raw = pipeline.connections["raw"]
            raw.execute("INSERT INTO documents VALUES (?,?,?,?,?)",
                        ("azure-updates", "feed:0", ITEM["id"], digest(body), body))
            raw.execute("INSERT INTO targets VALUES (?,?,?)", (ITEM["id"], "azure-updates", "feed:0"))
            raw.commit()
            cache = pipeline.connections["web_cache"]
            url = catalog()["records"][0]["sourceUrl"]
            cache.execute("INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?)", (
                url, url, digest(body), body, '"original-etag"', "Tue, 10 Nov 2026 10:00:00 GMT",
                "text/html", "2026-11-10T10:00:00Z", None,
            ))
            cache.execute("INSERT INTO record_links VALUES (?,?,?,?,?)", (ITEM["id"], url, "announcement", url, None))
            cache.commit()
            canonical = pipeline.connections["canonical"]
            canonical.execute("UPDATE retirements SET input_sha256=?,approved_sha256=? WHERE id=?",
                              ("stored-hash", "stored-hash", ITEM["id"]))
            canonical.execute("INSERT INTO provenance VALUES (?,?)", (
                ITEM["id"], packed({"hash": "old-hash", "bodyBase64": "DO_NOT_COPY_THIS_BODY"}),
            ))
            canonical.commit()

    def hashes(self):
        return {name: file_hash(self.db / f"{name}.sqlite") for name in DATABASES}

    def recovery_stores(self):
        with closing(sqlite3.connect(self.db / "raw.sqlite")) as connection:
            connection.executescript("""
                PRAGMA user_version=2;
                CREATE TABLE discovery_runs (
                    run_id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL,
                    completed_at TEXT, manifest_json TEXT, error TEXT);
                INSERT INTO discovery_runs VALUES (
                    'discovery-1', 'complete', '2026-11-10T09:00:00Z',
                    '2026-11-10T10:00:00Z', '{"ids":["a"]}', NULL);
            """)
        with closing(sqlite3.connect(self.db / "extracted.sqlite")) as connection:
            connection.executescript("""
                CREATE TABLE source_observation_heads (
                    kind TEXT NOT NULL, source_key TEXT NOT NULL, input_version TEXT NOT NULL,
                    extractor_version INTEGER NOT NULL, PRIMARY KEY(kind, source_key));
                CREATE TABLE source_observation_markers (
                    request_sha256 TEXT NOT NULL, extractor_version INTEGER NOT NULL,
                    marker_sha256 TEXT NOT NULL, request_json TEXT NOT NULL,
                    ticket_json TEXT NOT NULL, kind TEXT NOT NULL, source_key TEXT NOT NULL,
                    input_version TEXT NOT NULL, PRIMARY KEY(request_sha256, extractor_version));
                CREATE TABLE source_observation_versions (
                    kind TEXT NOT NULL, source_key TEXT NOT NULL, input_version TEXT NOT NULL,
                    extractor_version INTEGER NOT NULL, inputs_json TEXT NOT NULL,
                    observation_json TEXT NOT NULL,
                    PRIMARY KEY(kind, source_key, input_version, extractor_version));
                INSERT INTO source_observation_heads VALUES ('record','a','input-1',1);
                INSERT INTO source_observation_markers VALUES (
                    'request-1', 1, 'marker-1', '{"id":"a"}', '{"path":"evidence/marker.json"}',
                    'record', 'a', 'input-1');
                INSERT INTO source_observation_versions VALUES (
                    'record', 'a', 'input-1', 1, '{"sha256":"source-hash"}',
                    '{"status":"acquired","bodyBase64":"NOT_A_MIGRATED_BODY"}');
            """)
        root = self.root / "retained-evidence"
        root.mkdir()
        (root / "manifest.json").write_text('{"originalIds":["a"]}', encoding="utf-8")
        return root

    def test_raw_v2_and_observation_metadata_preserve_retained_evidence_references(self):
        evidence = self.recovery_stores()
        before = self.hashes()
        evidence_bytes = (evidence / "manifest.json").read_bytes()
        report = convert(self.db, self.destination, self.output, evidence_roots=[evidence])
        self.assertEqual(self.hashes(), before)
        self.assertEqual((evidence / "manifest.json").read_bytes(), evidence_bytes)
        self.assertEqual(report["databaseSchemaVersions"]["raw"], 2)
        self.assertEqual(report["unmappedAuxiliaryTables"], {})
        self.assertEqual(report["mappedAuxiliaryTables"]["extracted.source_observation_versions"], 1)
        self.assertTrue(report["readyToPublish"])
        self.assertEqual(report["retainedEvidenceFiles"], 1)
        automatic = json.loads((self.destination / f"{ENRICH_AUTO}.json").read_text(encoding="utf-8"))
        imported = automatic["sqliteImport"]
        rows = imported["auxiliaryMetadata"]["raw.discovery_runs"]
        self.assertEqual(rows[0]["completed_at"], "2026-11-10T10:00:00Z")
        self.assertEqual(rows[0]["manifest_json"], {"ids": ["a"]})
        marker = imported["auxiliaryMetadata"]["extracted.source_observation_markers"][0]
        self.assertEqual(marker["request_json"], {"id": "a"})
        self.assertEqual(marker["marker_sha256"], "marker-1")
        reference = imported["retainedEvidence"][0]["files"][0]
        self.assertEqual(reference["sha256"], file_hash(evidence / "manifest.json"))
        self.assertNotIn("NOT_A_MIGRATED_BODY", json.dumps(automatic))
        with Stages(self.destination) as stages:
            website = self.destination / "retirements.json"
            original = website.read_bytes()
            merge(stages, website)
            self.assertEqual(website.read_bytes(), original)

    def test_recovery_conversion_requires_evidence_roots_even_with_allow_unmapped(self):
        self.recovery_stores()
        report = convert(self.db, self.destination, dry_run=True)
        self.assertTrue(report["missingEvidenceRoots"])
        self.assertFalse(report["readyToPublish"])
        self.assertFalse(self.destination.exists())
        with self.assertRaisesRegex(ValueError, "requires retained journals/evidence"):
            convert(self.db, self.destination, allow_unmapped=True)

    def test_changed_evidence_discards_conversion(self):
        evidence = self.recovery_stores()
        original_hash = file_hash
        evidence_hashes = 0

        def mutate_evidence(path):
            nonlocal evidence_hashes
            if Path(path) == evidence / "manifest.json":
                evidence_hashes += 1
                if evidence_hashes == 2:
                    Path(path).write_text('{"changed":true}', encoding="utf-8")
            return original_hash(path)

        with patch("scripts.convert_enrichment.file_hash", side_effect=mutate_evidence):
            with self.assertRaisesRegex(ValueError, "Retained evidence changed"):
                convert(self.db, self.destination, evidence_roots=[evidence])
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob("converted.convert-*")))

    def test_open_evidence_journal_and_unknown_database_version_are_rejected(self):
        evidence = self.recovery_stores()
        journal = evidence / "journal.sqlite-wal"
        journal.touch()
        with self.assertRaisesRegex(ValueError, "Close/checkpoint evidence journals"):
            convert(self.db, self.destination, evidence_roots=[evidence])
        journal.unlink()
        with closing(sqlite3.connect(self.db / "raw.sqlite")) as connection:
            connection.execute("PRAGMA user_version=3")
        with self.assertRaisesRegex(ValueError, "Unsupported SQLite schema"):
            convert(self.db, self.destination, evidence_roots=[evidence])

    def test_raw_v2_requires_recognized_discovery_table_schema(self):
        with closing(sqlite3.connect(self.db / "raw.sqlite")) as connection:
            connection.executescript("""
                PRAGMA user_version=2;
                CREATE TABLE discovery_runs (id TEXT);
                INSERT INTO discovery_runs VALUES ('unknown');
            """)
        with self.assertRaisesRegex(ValueError, "Unsupported discovery_runs schema"):
            convert(self.db, self.destination, allow_unmapped=True)
        self.assertFalse(self.destination.exists())

    def test_lossless_read_only_conversion_and_merge_noop(self):
        before = self.hashes()
        report = convert(self.db, self.destination, self.output)
        self.assertEqual(self.hashes(), before)
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["storedApprovalsNotRevalidated"], 1)
        self.assertEqual(len(list(self.destination.iterdir())), 6)
        website = self.destination / "retirements.json"
        self.assertEqual(parse_catalog(json.loads(website.read_text(encoding="utf-8"))), catalog())
        with Stages(self.destination) as stages:
            canonical_view = stages.load(CANONICAL)
            self.assertEqual(canonical_view["records"]["a"], catalog()["records"][0])
            self.assertEqual(canonical_view["revisions"]["a"]["recordSha256"],
                             fingerprint(catalog()["records"][0]))
        original = website.read_bytes()
        with Stages(self.destination) as stages:
            merge(stages, website)
            automatic = stages.load(ENRICH_AUTO)
            imported = automatic["records"]["a"]
            self.assertEqual(imported["origin"], "sqlite-import")
            self.assertEqual(imported["importedProvenance"], {"hash": "old-hash"})
            page = next(iter(automatic["pages"].values()))
            self.assertEqual(page["etag"], '"original-etag"')
            self.assertIsNone(page["contentSha256"])
            self.assertEqual(page["status"], "imported")
            self.assertEqual(page["fetchedAt"], "2026-11-10T10:00:00Z")
            self.assertNotIn("legacy", json.dumps(automatic).lower())
        self.assertEqual(original, website.read_bytes())
        self.assertEqual(self.hashes(), before)
        self.assertFalse(any(path.suffix in (".sqlite", ".txt") for path in self.destination.rglob("*")))
        self.assertNotIn("DO_NOT_COPY_THIS_BODY", (self.destination / f"{ENRICH_AUTO}.json").read_text())
        with self.assertRaisesRegex(ValueError, "JSON enrichment"):
            refresh_catalog(fetcher=lambda _: self.fail("Conversion must not permit SQLite refresh"), output=website)

    def test_manual_fields_preserved_separately_and_composed_identically(self):
        with Pipeline(self.db, self.output) as pipeline:
            pipeline.manual({
                "catalogSha256": pipeline.status()["catalogSha256"],
                "overrides": [{"id": "a", "fields": {
                    "summary": "User summary", "customNotes": "Custom field",
                    "questions": {"impact": {"guidance": "User impact text."}},
                }}],
            })
            self.output.write_bytes(catalog_bytes(pipeline.catalog(automatic=False)))
        expected = json.loads(self.output.read_text(encoding="utf-8"))
        before = self.hashes()
        report = convert(self.db, self.destination, self.output)
        self.assertEqual(report["manualOverrides"], 1)
        with Stages(self.destination) as stages:
            manual = stages.load(ENRICH_MANUAL)
            self.assertEqual(manual["recordOverrides"]["a"]["customNotes"], "Custom field")
            self.assertNotEqual(stages.load(ENRICH_AUTO)["records"]["a"]["summary"], "User summary")
            canonical_view = stages.load(CANONICAL)
            self.assertEqual(canonical_view["records"]["a"], expected["records"][0])
            self.assertEqual(canonical_view["revisions"]["a"]["manualFieldsSha256"],
                             fingerprint(manual["recordOverrides"]["a"]))
            converted = self.destination / "retirements.json"
            original = converted.read_bytes()
            merge(stages, converted)
            self.assertEqual(converted.read_bytes(), original)
        self.assertEqual(parse_catalog(json.loads(converted.read_text(encoding="utf-8"))), expected)
        self.assertEqual(self.hashes(), before)

    def test_imported_manual_fields_survive_new_synthesis_and_explicit_removal(self):
        with Pipeline(self.db, self.output) as pipeline:
            pipeline.manual({
                "catalogSha256": pipeline.status()["catalogSha256"],
                "overrides": [{"id": "a", "fields": {"summary": "User summary", "customNotes": "Keep me"}}],
            })
        convert(self.db, self.destination)

        def fetch(url, previous, force):
            if "releasecommunications" in url:
                return {"status": 200, "body": json.dumps(ITEM).encode(),
                        "resolvedUrl": url, "headers": {"Content-Type": "application/json"}}
            return {"status": 200, "body": b"<main>Current migration guidance.</main>",
                    "resolvedUrl": url, "headers": {"Content-Type": "text/html"}}

        def summarize(payload):
            text = payload.get("userContext") or "Processed supplied page content."
            return {"summary": text, "questions": {key: text for key in QUESTIONS},
                    "deadline": {"date": None, "month": None}}

        with Stages(self.destination) as store:
            manual = store.load(ENRICH_MANUAL)
            manual["inputs"]["a"] = {"context": "User-provided team context."}
            store.save(ENRICH_MANUAL)
            engine = Enrichment(store, fetcher=fetch, summarizer=summarize)
            engine.download()
            engine.enrich()
            website = self.destination / "retirements.json"
            merge(store, website)
            record = json.loads(website.read_text(encoding="utf-8"))["records"][0]
            self.assertEqual(record["summary"], "User summary")
            self.assertEqual(record["customNotes"], "Keep me")
            self.assertIn("User-provided team context.", record["questions"]["what"]["announcement"])
            self.assertIn("enrichment", record)
            del manual["recordOverrides"]["a"]
            store.save(ENRICH_MANUAL)
            merge(store, website)
            record = json.loads(website.read_text(encoding="utf-8"))["records"][0]
            self.assertNotEqual(record["summary"], "User summary")
            self.assertNotIn("manualEnrichment", record)

    def test_manual_only_absent_record_retains_baseline(self):
        missing = copy.deepcopy(catalog()["records"][0])
        missing["id"] = "absent"
        missing["sourceUrl"] = "https://azure.microsoft.com/updates?id=absent"
        connection = sqlite3.connect(self.db / "manual.sqlite")
        with connection:
            connection.execute("INSERT INTO overrides VALUES (?,?,?)",
                               ("absent", packed({"summary": "Keep absent manual content"}), packed(missing)))
        connection.close()
        report = convert(self.db, self.destination)
        self.assertEqual(report["records"], 2)
        with Stages(self.destination) as store:
            merge(store, self.destination / "retirements.json")
        value = json.loads((self.destination / "retirements.json").read_text(encoding="utf-8"))
        self.assertEqual(value["records"][1]["id"], "absent")
        self.assertEqual(value["records"][1]["summary"], "Keep absent manual content")

    def test_non_azure_discovery_not_invented_as_manual_input(self):
        connection = sqlite3.connect(self.db / "canonical.sqlite")
        record = catalog()["records"][0]
        record["sourceUrl"] = "https://learn.microsoft.com/lifecycle/products/example"
        with connection:
            connection.execute("UPDATE retirements SET record_json=? WHERE id='a'", (packed(record),))
        connection.close()
        report = convert(self.db, self.destination)
        self.assertEqual(report["retainedOutsideDiscovery"], ["a"])
        manual = json.loads((self.destination / "retirement_source_manual.json").read_text())
        self.assertEqual(manual["records"], {})
        self.assertEqual(json.loads((self.destination / "retirements.json").read_text(encoding="utf-8"))["records"][0], record)
        with Stages(self.destination) as store:
            merge(store, self.destination / "retirements.json")

    def test_auxiliary_tables_are_reported_and_require_explicit_permission(self):
        connection = sqlite3.connect(self.db / "raw.sqlite")
        with connection:
            connection.execute("CREATE TABLE discovery_runs (id TEXT)")
            connection.execute("INSERT INTO discovery_runs VALUES ('run')")
        connection.close()
        report = convert(self.db, self.destination, dry_run=True)
        self.assertEqual(report["unmappedAuxiliaryTables"], {"raw.discovery_runs": 1})
        self.assertFalse(report["readyToPublish"])
        self.assertFalse(self.destination.exists())
        with self.assertRaisesRegex(ValueError, "Unmapped auxiliary"):
            convert(self.db, self.destination)
        convert(self.db, self.destination, allow_unmapped=True)
        self.assertTrue(self.destination.is_dir())

    def test_dry_run_no_destination_and_existing_destination_never_replaced(self):
        before = self.hashes()
        report = convert(self.db, self.destination, dry_run=True)
        self.assertTrue(report["dryRun"])
        self.assertFalse(self.destination.exists())
        convert(self.db, self.destination)
        marker = self.destination / "retirements.json"
        original = marker.read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            convert(self.db, self.destination)
        self.assertEqual(marker.read_bytes(), original)
        self.assertEqual(self.hashes(), before)

    def test_divergent_catalog_and_missing_store_fail_without_output(self):
        self.output.write_bytes(catalog_bytes({**catalog(), "retrievedAt": "2026-11-11T00:00:00Z"}))
        with self.assertRaisesRegex(ValueError, "differs"):
            convert(self.db, self.destination, self.output)
        self.assertFalse(self.destination.exists())
        (self.db / "manual.sqlite").rename(self.db / "manual.backup")
        with self.assertRaisesRegex(ValueError, "Missing SQLite store"):
            convert(self.db, self.destination)
        self.assertFalse(self.destination.exists())

    def test_lock_or_journal_blocks_conversion_without_removal(self):
        lock = self.db / ".lock"
        lock.write_text("1234")
        with self.assertRaisesRegex(ValueError, ".lock"):
            convert(self.db, self.destination)
        self.assertTrue(lock.exists())
        lock.unlink()
        journal = self.db / "canonical.sqlite-journal"
        journal.touch()
        with self.assertRaisesRegex(ValueError, "Close/checkpoint"):
            convert(self.db, self.destination)
        self.assertTrue(journal.exists())

    def test_changed_store_discards_staged_output(self):
        real_hash = file_hash
        count = 0

        def changed(path):
            nonlocal count
            count += 1
            return real_hash(path) if count <= 5 else "changed"

        with patch("scripts.convert_enrichment.file_hash", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "changed during conversion"):
                convert(self.db, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob("converted.convert-*")))

    def test_sidecar_appearing_during_conversion_blocks_publication(self):
        real_hash = file_hash
        count = 0
        sidecar = self.db / "canonical.sqlite-shm"

        def writer_started(path):
            nonlocal count
            count += 1
            if count == 6:
                sidecar.touch()
            return real_hash(path)

        with patch("scripts.convert_enrichment.file_hash", side_effect=writer_started):
            with self.assertRaisesRegex(ValueError, "changed during conversion"):
                convert(self.db, self.destination)
        self.assertTrue(sidecar.exists())
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob("converted.convert-*")))

    def test_imported_state_change_blocks_import_shortcut(self):
        convert(self.db, self.destination)
        with Stages(self.destination) as store:
            source = store.load(SOURCE_AUTO)
            source["pages"][next(iter(source["pages"]))]["contentSha256"] = "new-content"
            store.save(SOURCE_AUTO)
            with self.assertRaisesRegex(ValueError, "Imported inputs changed"):
                merge(store, self.destination / "retirements.json")

    def test_invalid_manual_fields_fail_without_publishing(self):
        connection = sqlite3.connect(self.db / "manual.sqlite")
        with connection:
            connection.execute("INSERT INTO overrides VALUES (?,?,?)",
                               ("a", packed({"id": "wrong"}), packed(catalog()["records"][0])))
        connection.close()
        with self.assertRaisesRegex(ValueError, "identity"):
            convert(self.db, self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
