import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from fixtures import ITEM, catalog
from scripts.pipeline import (
    ENDPOINT, EXTRACTOR_VERSION, Pipeline, PublicRedirects, catalog_bytes, digest,
    lifecycle_observation, public_url,
)

LIFECYCLE = "https://learn.microsoft.com/lifecycle/end-of-support/end-of-support-2027"
LIFE_BODY = b"""<!doctype html><meta charset="utf-8">
<h2>Additional Azure Changes</h2><table><tr><th>Item</th><th>Retirement</th></tr>
<tr><td><a href="https://azure.microsoft.com/updates/unrelated/">A neighboring product</a>
<a href="https://azure.microsoft.com/updates/a/">Selected classic SKU</a></td><td>March 31, 2027</td></tr></table>"""


class Response(io.BytesIO):
    status = 200

    def __init__(self, url, body, headers):
        super().__init__(body)
        self.url, self.headers = url, headers

    def geturl(self):
        return self.url


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.output = self.directory / "retirements.json"
        self.original = catalog()
        self.original["customCatalogMetadata"] = {"retained": [1, 2, 3]}
        record = self.original["records"][0]
        record["sourceReview"] = {
            "status": "enriched", "reviewedOn": "2026-11-12", "issues": [],
            "originalAnnouncement": record["questions"]["what"]["announcement"],
            "originalDeadline": {key: record["questions"]["deadline"][key] for key in ("date", "month")},
            "sources": [{"title": "Fixture guidance", "url": "https://learn.microsoft.com/azure/",
                         "sections": list(record["questions"]), "note": "Fixture evidence."}],
            "resourceChecks": [{"url": "https://learn.microsoft.com/azure/", "resolvedUrl": None,
                                "status": "not-evidence", "detail": "Fixture reference."}],
            "deadlineSource": "https://learn.microsoft.com/azure/",
        }
        for question in record["questions"].values():
            question["html"] = "<p>A reviewed answer.</p>"
        other = copy.deepcopy(record)
        other.update({"id": "b", "title": "Unrelated hidden retirement", "hidden": True,
                      "custom": {"retained": [1, 2, 3]}})
        self.original["records"].append(other)
        self.output.write_bytes(catalog_bytes(self.original))
        self.pipeline = Pipeline(self.directory / "databases", self.output)
        self.addCleanup(self.pipeline.close)
        self.pipeline.seed()
        self.requests = []
        self.bodies = {}
        self.headers = {}
        self.failures = {}
        self.mock = patch("scripts.pipeline.open_public", side_effect=self.fetch)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def fetch(self, request):
        url = request.full_url
        self.requests.append(request)
        if url in self.failures:
            raise self.failures[url]
        if url.startswith(ENDPOINT):
            body = json.dumps({"@odata.count": 1, "value": [ITEM]}).encode()
        elif url == LIFECYCLE:
            body = LIFE_BODY
        else:
            body = b"Public page: " + url.encode()
        body = self.bodies.get(url, body)
        headers = self.headers.get(url, {"ETag": '"' + digest(body) + '"', "Content-Type": "text/html"})
        if request.get_header("If-none-match") and request.get_header("If-none-match") == headers.get("ETag"):
            raise HTTPError(url, 304, "Not modified", headers, None)
        if request.get_header("If-modified-since") and request.get_header("If-modified-since") == headers.get("Last-Modified"):
            raise HTTPError(url, 304, "Not modified", headers, None)
        return Response(url, body, headers)

    def prepare(self):
        self.pipeline.ingest("a", LIFECYCLE)
        self.pipeline.extract("a")
        self.pipeline.links("a")

    def approve(self):
        proposal = self.pipeline.canonical("a")
        return self.pipeline.canonical("a", True, proposal["inputSha256"], proposal["recordSha256"])

    def snapshots(self):
        return {path.name: path.read_bytes() for path in self.pipeline.directory.glob("*.sqlite")}

    def manual_batch(self, fields):
        return {"catalogSha256": self.pipeline.status()["catalogSha256"],
                "overrides": [{"id": "a", "fields": fields}]}

    def test_manual_fields_override_research_without_changing_it_and_can_be_removed(self):
        self.prepare()
        self.approve()
        automatic = self.pipeline.catalog(automatic=True)
        patch_fields = {"summary": "User-provided summary.",
                        "questions": {"impact": {"guidance": "User-provided impact."}}}
        batch = self.manual_batch(patch_fields)
        self.assertEqual(self.pipeline.manual(batch)["changed"], 1)
        self.assertEqual(self.pipeline.catalog(automatic=True), automatic)
        self.assertFalse(self.pipeline.status()["targets"][0]["reviewRequired"])
        self.pipeline.export()
        record = json.loads(self.output.read_bytes())["records"][0]
        self.assertEqual(record["summary"], patch_fields["summary"])
        self.assertEqual(record["questions"]["impact"]["guidance"], "User-provided impact.")
        self.assertNotIn("html", record["questions"]["impact"])
        self.assertEqual(record["questions"]["actions"], automatic["records"][0]["questions"]["actions"])
        self.assertIn("questions.impact.guidance", record["manualEnrichment"]["fields"])
        with self.assertRaisesRegex(ValueError, "Catalog changed"):
            self.pipeline.manual(batch)
        before = self.snapshots()
        self.assertEqual(self.pipeline.manual(self.manual_batch(patch_fields))["changed"], 0)
        self.assertEqual(self.snapshots(), before)
        self.assertEqual(self.pipeline.seed()["seeded"], 0)
        self.pipeline.manual(self.manual_batch({"questions": {"impact": {
            "guidance": "First manual revision.", "html": "<p>First manual revision.</p>",
        }}}))
        self.pipeline.manual(self.manual_batch({"questions": {"impact": {"guidance": "Second manual revision."}}}))
        self.assertNotIn("html", self.pipeline.catalog()["records"][0]["questions"]["impact"])
        self.pipeline.manual(self.manual_batch(None))
        self.pipeline.export()
        self.assertEqual(json.loads(self.output.read_bytes()), automatic)

    def test_automatic_reviews_do_not_modify_or_absorb_manual_overrides(self):
        self.prepare()
        self.approve()
        self.pipeline.manual(self.manual_batch({"summary": "Manual summary."}))
        before = self.snapshots()["manual.sqlite"]
        record = self.original["records"][0]
        batch = {
            "catalogSha256": self.pipeline.status()["automaticCatalogSha256"],
            "reviews": [{"id": "a", "summary": "New automatic summary.",
                         "questions": {key: {} for key in record["questions"]},
                         "sourceReview": {key: value for key, value in record["sourceReview"].items()
                                          if key not in ("originalAnnouncement", "originalDeadline")}}],
        }
        self.pipeline.review(batch)
        self.approve()
        self.pipeline.export()
        self.assertEqual(self.pipeline.catalog()["records"][0]["summary"], "Manual summary.")
        self.assertEqual(self.pipeline.catalog(automatic=True)["records"][0]["summary"], "New automatic summary.")
        self.assertEqual(self.snapshots()["manual.sqlite"], before)

    def test_missing_manual_store_cannot_silently_discard_exported_content(self):
        self.pipeline.manual(self.manual_batch({"summary": "Manual summary."}))
        self.pipeline.export()
        directory = self.pipeline.directory
        self.pipeline.close()
        manual = directory / "manual.sqlite"
        manual.rename(directory / "manual.sqlite.backup")
        before, output = self.snapshots(), self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "Missing manual.sqlite"):
            with Pipeline(directory, self.output):
                pass
        self.assertEqual(self.snapshots(), before)
        self.assertEqual(self.output.read_bytes(), output)
        self.assertFalse(manual.exists())
        self.assertFalse((directory / ".lock").exists())

    def test_manual_batches_are_validated_atomically_and_preserve_unrelated_records(self):
        before = self.snapshots()
        for fields in ({"id": "replacement"}, {"questions": {"impact": {"question": "New heading"}}},
                       {"questions": {"impact": {"html": "<script>unsafe</script>"}}}, {"summary": None}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.pipeline.manual(self.manual_batch(fields))
            self.assertEqual(self.snapshots(), before)
        batch = self.manual_batch({"summary": "Valid first entry."})
        batch["overrides"].append({"id": "unknown", "fields": {"summary": "Invalid second entry."}})
        with self.assertRaisesRegex(ValueError, "Unknown retirement"):
            self.pipeline.manual(batch)
        self.assertEqual(self.snapshots(), before)

    def test_offline_migration_removes_flags_and_preserves_legacy_manual_content(self):
        legacy = copy.deepcopy(self.original)
        for record in legacy["records"]:
            record["manuallyEnriched"] = record["id"] == "a"
        legacy["records"][0]["customNotes"] = {"migration": "retained"}
        self.output.write_bytes(catalog_bytes(legacy))
        with self.pipeline.connections["canonical"] as connection:
            for record in legacy["records"]:
                connection.execute("UPDATE retirements SET record_json=? WHERE id=?",
                                   (json.dumps(record), record["id"]))
            connection.execute("UPDATE metadata SET value=? WHERE key='export_sha256'",
                               (digest(self.output.read_bytes()),))
        with patch("scripts.pipeline.open_public", side_effect=AssertionError("Migration attempted a download")):
            result = self.pipeline.migrate()
        self.assertEqual(result["migratedRecords"], 2)
        self.assertEqual(result["manualRecords"], 1)
        migrated = self.pipeline.catalog()
        self.assertFalse(any("manuallyEnriched" in record for record in migrated["records"]))
        self.assertEqual(migrated["records"][0]["questions"], self.original["records"][0]["questions"])
        self.assertEqual(migrated["records"][0]["customNotes"], {"migration": "retained"})
        self.assertEqual(migrated["records"][1], self.original["records"][1])
        before = self.snapshots()
        self.assertEqual(self.pipeline.migrate()["migratedRecords"], 0)
        self.assertEqual(self.snapshots(), before)

    def test_legacy_cache_names_fail_without_overwriting_either_file(self):
        self.prepare()
        self.approve()
        directory = self.pipeline.directory
        self.pipeline.close()
        cache = directory / "web_cache.sqlite"
        legacy = directory / "links.sqlite"
        cache.rename(legacy)
        for both_exist in (False, True):
            with self.subTest(both_exist=both_exist):
                if both_exist:
                    cache.write_bytes(legacy.read_bytes())
                before = self.snapshots()
                with self.assertRaisesRegex(ValueError, "Legacy links.sqlite"):
                    with Pipeline(directory, self.output):
                        pass
                self.assertEqual(self.snapshots(), before)
                self.assertFalse((directory / ".lock").exists())
        legacy.unlink()
        with Pipeline(directory, self.output) as reopened:
            self.assertIsNotNone(reopened.page(LIFECYCLE)["body"])
            self.assertFalse(reopened.export()["changed"])

    def test_full_pilot_preserves_all_records_and_noop_is_byte_identical(self):
        self.prepare()
        self.assertFalse(self.approve()["reviewRequired"])
        self.assertFalse(self.pipeline.export()["changed"])
        before, output = self.snapshots(), self.output.read_bytes()
        self.assertEqual(self.pipeline.seed()["seeded"], 0)
        self.assertEqual(self.pipeline.ingest("a", LIFECYCLE)["changedDocuments"], 0)
        self.assertEqual(self.pipeline.extract("a"), {"extracted": 0, "unchanged": 2})
        self.assertTrue(all(result["outcome"] in ("not-modified", "reused-source")
                            for result in self.pipeline.links("a")["requests"]))
        self.assertFalse(self.approve()["changed"])
        self.assertFalse(self.pipeline.export()["changed"])
        self.assertEqual(self.snapshots(), before)
        self.assertEqual(self.output.read_bytes(), output)
        self.assertEqual(json.loads(output), self.original)

    def test_conditional_last_modified_and_no_validator_hash_comparison(self):
        url = "https://learn.microsoft.com/azure/example"
        self.headers[url] = {"Last-Modified": "Wed, 11 Nov 2026 10:00:00 GMT"}
        self.pipeline.download(url)
        before = self.snapshots()
        self.assertEqual(self.pipeline.download(url)["outcome"], "not-modified")
        self.assertEqual(self.requests[-1].get_header("If-modified-since"), self.headers[url]["Last-Modified"])
        self.assertEqual(self.snapshots(), before)
        self.headers[url] = {}
        self.pipeline.download(url)
        before = self.snapshots()
        result = self.pipeline.download(url)
        self.assertEqual(result["outcome"], "identical")
        self.assertFalse(result["validator"])
        self.assertEqual(self.snapshots(), before)

    def test_changed_source_requires_extraction_and_new_explicit_approval(self):
        self.prepare()
        old = self.approve()
        api = next(request.full_url for request in self.requests if request.full_url.startswith(ENDPOINT))
        item = {**ITEM, "description": "<p>Changed source facts.</p>"}
        self.bodies[api] = json.dumps({"@odata.count": 1, "value": [item]}).encode()
        self.pipeline.ingest("a", LIFECYCLE)
        with self.assertRaisesRegex(ValueError, "stale extracted"):
            self.pipeline.export()
        self.assertEqual(self.pipeline.extract("a"), {"extracted": 1, "unchanged": 1})
        self.assertTrue(self.pipeline.canonical("a")["reviewRequired"])
        with self.assertRaisesRegex(ValueError, "fingerprints changed"):
            self.pipeline.canonical("a", True, old["inputSha256"], old["recordSha256"])
        with self.assertRaisesRegex(ValueError, "unapproved"):
            self.pipeline.export()
        self.assertEqual(self.pipeline.catalog(), self.original)

    def test_changed_document_invalidates_review_but_validator_only_change_does_not(self):
        self.prepare()
        self.approve()
        url = "https://learn.microsoft.com/azure/"
        self.headers[url] = {"ETag": '"new-validator"'}
        self.pipeline.download(url)
        self.assertFalse(self.pipeline.canonical("a")["reviewRequired"])
        self.bodies[url] = b"Changed documentation"
        self.headers[url] = {"ETag": '"changed-content"'}
        self.pipeline.download(url)
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.pipeline.export()
        self.assertTrue(self.pipeline.status()["targets"][0]["reviewRequired"])
        self.assertTrue(self.pipeline.canonical("a")["reviewRequired"])

    def test_failed_checks_preserve_body_and_block_export_until_revalidated(self):
        self.prepare()
        self.approve()
        url = "https://learn.microsoft.com/azure/"
        body = self.pipeline.page(url)["body"]
        self.failures[url] = HTTPError(url, 403, "Forbidden", {}, None)
        with self.assertRaises(HTTPError):
            self.pipeline.download(url)
        self.assertEqual(self.pipeline.page(url)["body"], body)
        with self.assertRaisesRegex(ValueError, "failed link"):
            self.pipeline.export()
        del self.failures[url]
        self.assertEqual(self.pipeline.download(url)["outcome"], "not-modified")
        self.assertFalse(self.pipeline.export()["changed"])

    def test_partial_ingest_does_not_replace_raw_and_retries_are_bounded(self):
        self.prepare()
        self.approve()
        before = self.snapshots()["raw.sqlite"]
        self.failures[LIFECYCLE] = HTTPError(LIFECYCLE, 503, "Unavailable", {"Retry-After": "0"}, None)
        with patch("scripts.pipeline.time.sleep") as sleep, self.assertRaises(HTTPError):
            self.pipeline.ingest("a", LIFECYCLE)
        self.assertEqual(sleep.call_count, 4)
        self.assertEqual(self.snapshots()["raw.sqlite"], before)
        self.assertIsNotNone(self.pipeline.page(LIFECYCLE)["body"])
        with self.assertRaisesRegex(ValueError, "cache changed/failed"):
            self.pipeline.export()

    def test_export_requires_assembly_approval_and_rejects_external_json_changes(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "Missing canonical"):
            self.pipeline.export()
        self.pipeline.canonical("a")
        with self.assertRaisesRegex(ValueError, "unapproved"):
            self.pipeline.export()
        self.approve()
        changed = copy.deepcopy(self.original)
        changed["records"][1]["summary"] = "An external edit."
        self.output.write_bytes(catalog_bytes(changed))
        with self.assertRaisesRegex(ValueError, "changed outside"):
            self.pipeline.export()
        self.assertEqual(json.loads(self.output.read_bytes()), changed)

    def test_review_stage_uses_existing_guarded_editor_and_exports_from_database(self):
        self.prepare()
        self.approve()
        batch = {
            "catalogSha256": digest(catalog_bytes(self.pipeline.catalog())),
            "reviews": [{"id": "a", "summary": "New reviewed summary.",
                         "questions": {key: {} for key in self.original["records"][0]["questions"]},
                         "sourceReview": {key: value for key, value in self.original["records"][0]["sourceReview"].items()
                                          if key not in ("originalAnnouncement", "originalDeadline")}}],
        }
        self.pipeline.review(batch)
        with self.assertRaisesRegex(ValueError, "unapproved"):
            self.pipeline.export()
        self.approve()
        self.assertTrue(self.pipeline.export()["changed"])
        exported = json.loads(self.output.read_bytes())
        self.assertEqual(exported["records"][0]["summary"], "New reviewed summary.")
        self.assertEqual(exported["records"][1], self.original["records"][1])
        self.assertEqual(exported["records"][0]["sourceReview"]["originalAnnouncement"],
                         self.original["records"][0]["sourceReview"]["originalAnnouncement"])
        with self.assertRaisesRegex(ValueError, "Catalog changed"):
            self.pipeline.review(batch)
        self.output.unlink()
        self.assertTrue(self.pipeline.export()["changed"])
        self.assertEqual(json.loads(self.output.read_bytes()), exported)

    def test_lifecycle_identity_uses_only_exact_cross_reference_not_neighbor(self):
        observation = lifecycle_observation(LIFE_BODY, "a")
        self.assertEqual(observation["title"], "Selected classic SKU")
        self.assertEqual(observation["provisionalDate"], "2027-03-31")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            lifecycle_observation(LIFE_BODY, "missing")

    def test_extractor_version_invalidates_without_network_and_hidden_targets_are_rejected(self):
        self.prepare()
        with patch("scripts.pipeline.EXTRACTOR_VERSION", EXTRACTOR_VERSION + 1):
            count = len(self.requests)
            self.assertEqual(self.pipeline.extract("a")["extracted"], 2)
            self.assertEqual(len(self.requests), count)
        with self.assertRaisesRegex(ValueError, "Hidden"):
            self.pipeline.ingest("b", LIFECYCLE)

    def test_identical_body_under_a_new_source_key_updates_extracted_provenance(self):
        self.prepare()
        localized = "https://learn.microsoft.com/en-us/lifecycle/end-of-support/end-of-support-2027"
        self.bodies[localized] = LIFE_BODY
        self.pipeline.ingest("a", localized)
        self.assertEqual(self.pipeline.extract("a"), {"extracted": 1, "unchanged": 1})
        row = self.pipeline.connections["extracted"].execute(
            "SELECT source_key FROM observations WHERE retirement_id='a' AND source='lifecycle'",
        ).fetchone()
        self.assertEqual(row[0], localized)

    def test_links_do_not_refetch_raw_sources_owned_by_ingest(self):
        self.prepare()
        self.requests.clear()
        results = self.pipeline.links("a")["requests"]
        self.assertEqual(sum(result["outcome"] == "reused-source" for result in results), 2)
        self.assertFalse(any(request.full_url.startswith(ENDPOINT) or request.full_url == LIFECYCLE
                             for request in self.requests))

    def test_redirects_and_private_or_non_microsoft_urls_are_rejected(self):
        for url in ("http://learn.microsoft.com/azure/", "https://127.0.0.1/", "https://example.com/",
                    "https://learn.microsoft.com:8443/", "https://user:password@learn.microsoft.com/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                public_url(url)
        with patch("scripts.pipeline.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("127.0.0.1", 443))]):
            with self.assertRaisesRegex(ValueError, "Private"):
                public_url("https://learn.microsoft.com/azure/", resolve=True)
        with self.assertRaises(ValueError):
            PublicRedirects().redirect_request(Request(LIFECYCLE), None, 302, "", {}, "https://portal.azure.com/")

    def test_response_limits_fail_visibly_and_only_one_writer_can_open_the_stores(self):
        url = "https://learn.microsoft.com/azure/example"
        self.bodies[url] = b"12345"
        with patch("scripts.pipeline.MAX_BYTES", 4), self.assertRaisesRegex(ValueError, "exceeds"):
            self.pipeline.download(url)
        self.assertIsNotNone(self.pipeline.page(url)["error"])
        with self.assertRaises(FileExistsError):
            Pipeline(self.pipeline.directory, self.output)
        self.assertEqual(self.pipeline.connections["canonical"].execute("PRAGMA journal_mode").fetchone()[0], "delete")
        for connection in self.pipeline.connections.values():
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_changed_redirect_does_not_reuse_an_old_body_on_304(self):
        url = "https://aka.ms/example"
        self.pipeline.download(url)
        destination = "https://learn.microsoft.com/azure/new-destination"
        requests = []

        def redirected(request):
            requests.append(request)
            if request.get_header("If-none-match"):
                raise HTTPError(destination, 304, "Not modified", {}, None)
            return Response(destination, b"New destination body", {"ETag": '"new"'})

        with patch("scripts.pipeline.open_public", side_effect=redirected):
            self.assertEqual(self.pipeline.download(url)["outcome"], "downloaded")
        self.assertEqual(len(requests), 2)
        self.assertIsNone(requests[1].get_header("If-none-match"))
        self.assertEqual(self.pipeline.page(url)["resolved_url"], destination)
        self.assertEqual(self.pipeline.page(url)["body"], b"New destination body")

    def test_truncated_200_does_not_replace_a_complete_cached_body(self):
        url = "https://learn.microsoft.com/azure/example"
        self.pipeline.download(url)
        previous = self.pipeline.page(url)["body"]
        with patch("scripts.pipeline.open_public", return_value=Response(url, b"Short", {"Content-Length": "50"})):
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                self.pipeline.download(url)
        self.assertEqual(self.pipeline.page(url)["body"], previous)
        self.assertIsNotNone(self.pipeline.page(url)["error"])
