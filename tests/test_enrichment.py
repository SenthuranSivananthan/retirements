import copy
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from html5lib import parseFragment

from scripts.catalog import QUESTIONS, parse_catalog, valid_question_html
from scripts.enrichment import (
    CANONICAL, ENRICH_AUTO, ENRICH_MANUAL, SOURCE_AUTO, SOURCE_MANUAL,
    Enrichment, command_adapter, discover, format_answer, main, merge, reprocess_record,
    valid_summary, validate_canonical,
)
from scripts.enrichment_http import DownloadError, extract_content, fetch_http, public_url, sha256
from scripts.enrichment_json import STAGES, Stages, fingerprint, write_json
from scripts.refresh_data import refresh_catalog
from fixtures import ITEM, catalog

ROOT_URL = "https://example.com/retirement"
REFERENCE = "https://learn.microsoft.com/azure/example"
GRANDCHILD = "https://example.com/never-follow"


def summary(text="The supplied content describes this retirement."):
    return {
        "summary": text,
        "questions": {key: f"{key}: {text}" for key in QUESTIONS},
        "deadline": {"date": None, "month": None},
    }


class FixtureFetcher:
    def __init__(self):
        self.bodies = {
            ROOT_URL: '<title>Retirement</title><main><p>Feature retires.</p>'
                      f'<a href="{REFERENCE}">Migration</a></main><nav><a href="{GRANDCHILD}">Nav</a></nav>',
            REFERENCE: f'<main><p>Migration steps.</p><a href="{GRANDCHILD}">More</a></main>',
        }
        self.calls = []
        self.failures = set()

    def __call__(self, url, previous=None, force=False):
        self.calls.append((url, force))
        if url in self.failures:
            raise DownloadError(f"HTTP 404: {url}")
        body = self.bodies[url].encode()
        etag = '"' + sha256(body) + '"'
        if not force and previous and previous.get("etag") == etag:
            return {"status": 304, "headers": {"ETag": etag}}
        return {
            "status": 200, "body": body, "resolvedUrl": url,
            "headers": {"Content-Type": "text/html", "ETag": etag},
        }


class JSONEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.store = Stages(self.directory).__enter__()
        self.store.initialize()
        source = self.store.load(SOURCE_MANUAL)
        source["records"]["manual-id"] = {"title": "Feature retirement", "urls": [ROOT_URL]}
        self.store.save(SOURCE_MANUAL)
        self.fetch = FixtureFetcher()
        self.payloads = []

        def summarize(payload):
            self.payloads.append(copy.deepcopy(payload))
            return summary("Summary of " + (payload.get("url") or payload.get("title", "content")))

        self.summarize = summarize
        self.engine = self.new_engine()

    def tearDown(self):
        self.store.__exit__(None, None, None)
        self.temporary.cleanup()

    def new_engine(self, **kwargs):
        return Enrichment(self.store, fetcher=self.fetch, summarizer=self.summarize, **kwargs)

    def run_pipeline(self, engine=None):
        engine = engine or self.engine
        engine.download()
        engine.enrich()
        output = self.directory / "retirements.json"
        merge(self.store, output)
        return output

    def test_pipeline_five_json_stages_depth_one_and_website_contract(self):
        output = self.run_pipeline()
        value = parse_catalog(json.loads(output.read_text(encoding="utf-8")))
        self.assertEqual(value["records"][0]["id"], "manual-id")
        self.assertEqual(value["records"][0]["sourceLabel"], "User-provided retirement")
        self.assertEqual(len([payload for payload in self.payloads if payload["kind"] == "page"]), 2)
        self.assertNotIn(GRANDCHILD, [url for url, _ in self.fetch.calls])
        self.assertEqual(set(value["records"][0]["questions"]), set(QUESTIONS))
        self.assertEqual(len(list(self.directory.glob("*.json"))), 6)
        self.assertFalse(list(self.store.work.glob("*.txt")))
        self.assertFalse(list(self.directory.glob("*.sqlite")))
        self.assertIn("team's", value["records"][0]["questions"]["progress"]["storageNote"])
        for name in STAGES:
            body = (self.directory / f"{name}.json").read_text(encoding="utf-8")
            self.assertTrue(body.endswith("\n"))
            self.assertNotIn('"body":', body)
        self.assertNotIn("content", self.engine.seen.get((ROOT_URL, False), {}))
        canonical = json.loads((self.directory / f"{CANONICAL}.json").read_text(encoding="utf-8"))
        record = value["records"][0]
        self.assertEqual(canonical["records"]["manual-id"], record)
        self.assertEqual(canonical["revisions"]["manual-id"]["recordSha256"], fingerprint(record))
        self.assertEqual(canonical["projectionRevision"], fingerprint(value))

    def test_canonical_view_is_authoritative_and_detects_website_divergence(self):
        output = self.run_pipeline()
        original = output.read_bytes()
        canonical_path = self.directory / f"{CANONICAL}.json"
        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        self.assertIn("automaticInputRevision", canonical["revisions"]["manual-id"])
        website = json.loads(original)
        website["records"][0]["summary"] = "Out-of-band edit"
        output.write_text(json.dumps(website), encoding="utf-8")
        changed_website = output.read_bytes()
        with self.assertRaisesRegex(ValueError, "differs from retirements_canonical"):
            merge(self.store, output)
        self.assertEqual(output.read_bytes(), changed_website)
        canonical_original = canonical_path.read_bytes()
        output.unlink()
        merge(self.store, output)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["records"][0]["summary"],
                         "Summary of Feature retirement")
        self.assertEqual(canonical_path.read_bytes(), canonical_original)

    def test_reprocess_refreshes_only_requested_retirement_through_projection(self):
        untouched_url = "https://example.com/untouched-retirement"
        manual_url = "https://example.com/selected-manual-input"
        untouched_manual_url = "https://example.com/untouched-manual-input"
        self.fetch.bodies[untouched_url] = "<main><p>Unchanged source.</p></main>"
        self.fetch.bodies[manual_url] = "<main><p>Selected manual guidance.</p></main>"
        self.fetch.bodies[untouched_manual_url] = "<main><p>Unchanged manual guidance.</p></main>"
        source = self.store.load(SOURCE_MANUAL)
        source["records"]["untouched-id"] = {
            "title": "Untouched retirement", "urls": [untouched_url],
        }
        self.store.save(SOURCE_MANUAL)
        manual = self.store.load(ENRICH_MANUAL)
        manual["inputs"]["manual-id"] = {"urls": [manual_url], "context": "Selected context"}
        manual["inputs"]["untouched-id"] = {
            "urls": [untouched_manual_url], "context": "Unchanged context",
        }
        self.store.save(ENRICH_MANUAL)
        output = self.run_pipeline()
        before = parse_catalog(json.loads(output.read_text(encoding="utf-8")))
        before_records = {record["id"]: record for record in before["records"]}
        self.fetch.calls.clear()
        self.payloads.clear()
        self.fetch.bodies[ROOT_URL] += "<p>Updated source content.</p>"
        def summarize(payload):
            self.payloads.append(copy.deepcopy(payload))
            return summary(
                "Reprocessed " + payload["id"] if payload["kind"] == "retirement"
                else "Refreshed page " + payload.get("url", "")
            )
        self.summarize = summarize
        engine = self.new_engine()

        result = reprocess_record(self.store, "manual-id", engine, output)

        after = parse_catalog(json.loads(output.read_text(encoding="utf-8")))
        after_records = {record["id"]: record for record in after["records"]}
        self.assertEqual(result["reprocessed"], "manual-id")
        self.assertTrue(after_records["manual-id"]["summary"].startswith("Reprocessed manual-id"))
        self.assertEqual(after_records["untouched-id"], before_records["untouched-id"])
        self.assertIn((ROOT_URL, True), self.fetch.calls)
        self.assertIn((REFERENCE, True), self.fetch.calls)
        self.assertIn((manual_url, True), self.fetch.calls)
        self.assertNotIn((untouched_url, True), self.fetch.calls)
        self.assertNotIn((untouched_manual_url, True), self.fetch.calls)
        retirement_payloads = [payload for payload in self.payloads if payload["kind"] == "retirement"]
        self.assertEqual({payload["id"] for payload in retirement_payloads}, {"manual-id"})
        self.assertEqual({payload["layer"] for payload in retirement_payloads},
                         {ENRICH_AUTO, ENRICH_MANUAL})

    def test_modified_canonical_record_fails_its_revision_guard(self):
        output = self.run_pipeline()
        canonical_path = self.directory / f"{CANONICAL}.json"
        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        canonical["records"]["manual-id"]["summary"] = "Out-of-band canonical edit"
        with self.assertRaisesRegex(ValueError, "Canonical record changed outside processing"):
            validate_canonical(canonical)

    def test_interrupted_projection_is_retried_without_overwriting_other_edits(self):
        output = self.run_pipeline()
        original = output.read_bytes()
        output.unlink()
        with patch("scripts.enrichment.write_json", side_effect=ValueError("simulated projection failure")):
            with self.assertRaisesRegex(ValueError, "simulated projection failure"):
                merge(self.store, output)
        canonical = json.loads((self.directory / f"{CANONICAL}.json").read_text(encoding="utf-8"))
        self.assertIn("pendingProjection", canonical)

        external = json.loads(original)
        external["records"][0]["summary"] = "Concurrent website edit"
        output.write_text(json.dumps(external), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Website catalog changed during a pending projection"):
            merge(self.store, output)
        self.assertIn("Concurrent website edit", output.read_text(encoding="utf-8"))
        output.unlink()

        merge(self.store, output)
        self.assertNotIn("pendingProjection", json.loads(
            (self.directory / f"{CANONICAL}.json").read_text(encoding="utf-8")
        ))
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["records"][0]["summary"],
                         "Summary of Feature retirement")

    def test_unchanged_304_reuses_summaries_and_preserves_output_bytes(self):
        output = self.run_pipeline()
        before = output.read_bytes()
        self.payloads.clear()
        self.run_pipeline(self.new_engine())
        self.assertFalse(self.payloads)
        self.assertEqual(output.read_bytes(), before)
        self.assertTrue(all(not force for _, force in self.fetch.calls))

    def test_rich_answers_and_manual_overrides_export_aligned_html_and_plain_text(self):
        rich = (
            "### Scope\n\nAffected **classic** instances only.\n\n"
            "- Check the `sku` value.\n- Keep *exceptions* visible.\n\n"
            "### Migration\n\n1. Inventory affected instances.\n2. Validate the replacement.\n\n"
            "```text\nsku == \"classic\" && enabled\n```\n\n"
            "Record results locally.\nKeep owners informed."
        )
        self.engine.summarizer = lambda _: {
            "summary": "Retirement scope and migration plan.",
            "questions": {key: rich for key in QUESTIONS},
            "deadline": {"date": None, "month": None},
        }
        manual = self.store.load(ENRICH_MANUAL)
        manual["inputs"]["manual-id"] = {
            "context": "Owner-approved plan",
            "overrides": {"questions": {"actions": "### Team plan\n\n1. Assign an **owner**.\n2. Verify `sku`."}},
        }
        self.store.save(ENRICH_MANUAL)
        output = self.run_pipeline()
        record = parse_catalog(json.loads(output.read_text(encoding="utf-8")))["records"][0]
        for key in QUESTIONS:
            question = record["questions"][key]
            self.assertTrue(valid_question_html(question["html"]))
            fragment = parseFragment(question["html"], namespaceHTMLElements=False)
            self.assertIsNotNone(fragment.find("h3"))
            self.assertIsNotNone(fragment.find("ol/li"))
        what = record["questions"]["what"]
        fragment = parseFragment(what["html"], namespaceHTMLElements=False)
        self.assertEqual(fragment.find("p/strong").text, "classic")
        self.assertEqual(fragment.find("ul/li/code").text, "sku")
        self.assertIn('sku == "classic" && enabled', fragment.find("pre/code").text)
        self.assertIsNotNone(fragment.find("p/br"))
        self.assertNotIn("###", what["announcement"])
        self.assertNotIn("**", what["announcement"])
        self.assertNotIn("```", what["announcement"])
        self.assertIn("Affected classic instances only.", what["announcement"])
        self.assertIn("- Check the sku value.", what["announcement"])
        self.assertIn("1. Inventory affected instances.", what["announcement"])
        self.assertIn("2. Validate the replacement.", what["announcement"])
        self.assertIn('sku == "classic" && enabled', what["announcement"])
        self.assertEqual(record["questions"]["actions"]["guidance"], "Team plan\n\n1. Assign an owner.\n2. Verify sku.")
        before = output.read_bytes()
        merge(self.store, output)
        self.assertEqual(output.read_bytes(), before)

    def test_identical_200_does_not_repeat_synthesis(self):
        self.run_pipeline()
        real_fetch = self.fetch

        def no_validator(url, previous, force):
            return real_fetch(url, previous, True)

        self.payloads.clear()
        engine = self.new_engine()
        engine.fetcher = no_validator
        self.run_pipeline(engine)
        self.assertFalse(self.payloads)

    def test_reference_change_reprocesses_only_reference_and_retirement(self):
        self.run_pipeline()
        self.fetch.bodies[REFERENCE] = "<main><p>New migration steps.</p></main>"
        self.payloads.clear()
        self.run_pipeline(self.new_engine())
        self.assertEqual([payload["kind"] for payload in self.payloads], ["page", "retirement"])
        self.assertEqual(self.payloads[0]["url"], REFERENCE)

    def test_processor_version_change_refetches_discarded_content(self):
        self.run_pipeline()
        self.payloads.clear()
        engine = self.new_engine(version="next-processor")
        engine.download()
        engine.enrich()
        self.assertEqual(sum(payload["kind"] == "page" for payload in self.payloads), 2)
        self.assertIn((ROOT_URL, True), self.fetch.calls)
        self.assertIn((REFERENCE, True), self.fetch.calls)

    def test_missing_summary_on_304_refetches_body(self):
        self.run_pipeline()
        stage = self.store.load(ENRICH_AUTO)
        stage["pages"][REFERENCE].pop("summary")
        self.store.save(ENRICH_AUTO)
        self.payloads.clear()
        self.run_pipeline(self.new_engine())
        self.assertEqual(self.payloads[0]["url"], REFERENCE)
        self.assertIn((REFERENCE, True), self.fetch.calls)

    def test_missing_root_summary_and_changed_refetched_body_update_reference_set(self):
        self.run_pipeline()
        stage = self.store.load(ENRICH_AUTO)
        stage["pages"][ROOT_URL].pop("summary")
        self.store.save(ENRICH_AUTO)
        replacement = "https://example.com/new-root-reference"
        self.fetch.bodies[replacement] = "<main>New replacement guidance</main>"
        self.fetch.bodies[ROOT_URL] = f'<main>New root<a href="{replacement}">Replacement</a></main>'
        # Source metadata is still the old revision; direct enrich must refresh
        # discarded content and guard that new root revision before export.
        self.payloads.clear()
        self.new_engine().enrich()
        output = self.directory / "retirements.json"
        merge(self.store, output)
        self.assertIn(replacement, self.payloads[-1]["documents"])
        self.assertNotIn(REFERENCE, self.payloads[-1]["documents"])

    def test_new_source_references_replace_removed_references(self):
        self.run_pipeline()
        second = "https://example.com/new-reference"
        self.fetch.bodies[ROOT_URL] = f'<main><p>Updated</p><a href="{second}">New</a></main>'
        self.fetch.bodies[second] = "<main>Replacement instructions</main>"
        self.payloads.clear()
        self.fetch.calls.clear()
        self.run_pipeline(self.new_engine())
        self.assertNotIn(REFERENCE, [url for url, _ in self.fetch.calls])
        self.assertIn(second, self.payloads[-1]["documents"])
        self.assertNotIn(REFERENCE, self.payloads[-1]["documents"])

    def test_failed_root_remains_explicit_and_blocks_export(self):
        output = self.run_pipeline()
        before = output.read_bytes()
        self.fetch.failures.add(ROOT_URL)
        with self.assertRaisesRegex(ValueError, "source downloads failed"):
            self.new_engine().download()
        self.assertEqual(self.store.load(SOURCE_MANUAL)["pages"][ROOT_URL]["status"], "failed")
        with self.assertRaisesRegex(ValueError, "acquisition"):
            merge(self.store, output)
        self.assertEqual(output.read_bytes(), before)

    def test_failed_reference_is_explicit_in_summary_payload_and_export(self):
        self.fetch.failures.add(REFERENCE)
        output = self.run_pipeline()
        self.assertIn(REFERENCE, self.payloads[-1]["unavailableReferences"][0])
        record = json.loads(output.read_text(encoding="utf-8"))["records"][0]
        self.assertIn("404", record["enrichment"]["issues"][0])
        self.assertNotIn(REFERENCE, [link["url"] for link in record["questions"]["actions"]["resources"]])

    def test_manual_links_context_and_field_level_overrides(self):
        manual_url = "https://example.com/my-reference"
        self.fetch.bodies[manual_url] = f'<main>Team instructions<a href="{GRANDCHILD}">More</a></main>'
        manual = self.store.load(ENRICH_MANUAL)
        manual["inputs"]["manual-id"] = {
            "urls": [manual_url], "context": "Team owns 12 affected resources.",
            "overrides": {"questions": {"actions": "Owner-approved migration plan."}},
        }
        self.store.save(ENRICH_MANUAL)
        output = self.run_pipeline()
        record = json.loads(output.read_text(encoding="utf-8"))["records"][0]
        self.assertEqual(record["questions"]["actions"]["guidance"], "Owner-approved migration plan.")
        self.assertIn("User-provided enrichment:", record["questions"]["what"]["announcement"])
        self.assertNotIn(GRANDCHILD, [url for url, _ in self.fetch.calls])
        self.assertEqual(self.payloads[-1]["userContext"], "Team owns 12 affected resources.")
        self.assertEqual(manual["inputs"]["manual-id"]["context"], "Team owns 12 affected resources.")

    def test_context_only_and_changes_do_not_repeat_automatic_summaries(self):
        manual = self.store.load(ENRICH_MANUAL)
        manual["inputs"]["manual-id"] = {"context": "Owner is platform team"}
        self.store.save(ENRICH_MANUAL)
        self.run_pipeline()
        self.payloads.clear()
        manual["inputs"]["manual-id"]["context"] = "Owner is application team"
        self.store.save(ENRICH_MANUAL)
        self.run_pipeline(self.new_engine())
        self.assertEqual(len(self.payloads), 1)
        self.assertEqual(self.payloads[0]["layer"], ENRICH_MANUAL)

    def test_changed_manual_input_cannot_merge_before_reprocessing(self):
        manual = self.store.load(ENRICH_MANUAL)
        manual["inputs"]["manual-id"] = {"context": "Version one"}
        self.store.save(ENRICH_MANUAL)
        output = self.run_pipeline()
        original = output.read_bytes()
        manual["inputs"]["manual-id"]["context"] = "Version two"
        self.store.save(ENRICH_MANUAL)
        with self.assertRaisesRegex(ValueError, "stale manual"):
            merge(self.store, output)
        self.assertEqual(output.read_bytes(), original)

    def test_new_source_revision_blocks_stale_export(self):
        output = self.run_pipeline()
        self.fetch.bodies[ROOT_URL] = "<main>Revised retirement content</main>"
        self.new_engine().download()
        with self.assertRaisesRegex(ValueError, "changed after enrichment"):
            merge(self.store, output)

    def test_mcp_full_content_preferred_without_fabricated_validators(self):
        def learn(payload):
            return {"content": f"# Guide\nMigration steps. [More]({GRANDCHILD})", "url": payload["url"]}

        engine = self.new_engine(learn_fetch=learn)
        self.run_pipeline(engine)
        page = self.store.load(ENRICH_AUTO)["pages"][REFERENCE]
        self.assertEqual(page["method"], "microsoft-learn-mcp")
        self.assertIsNone(page["etag"])
        self.assertNotIn("httpSha256", page)
        self.assertNotIn(REFERENCE, [url for url, _ in self.fetch.calls])
        self.assertNotIn(GRANDCHILD, [url for url, _ in self.fetch.calls])

    def test_mcp_failure_records_http_fallback(self):
        def learn(_):
            raise ValueError("MCP disconnected")

        self.run_pipeline(self.new_engine(learn_fetch=learn))
        page = self.store.load(ENRICH_AUTO)["pages"][REFERENCE]
        self.assertEqual(page["method"], "http")
        self.assertEqual(page["mcpError"], "MCP disconnected")

    def test_many_targets_checkpoint_partial_flush_and_resume(self):
        sources = self.store.load(SOURCE_MANUAL)
        for index in range(10):
            url = f"https://example.com/r{index}"
            sources["records"][f"r{index}"] = {"title": f"Retirement {index}", "urls": [url]}
            self.fetch.bodies[url] = f"<main>Distinct content {index}</main>"
        self.store.save(SOURCE_MANUAL)
        self.run_pipeline()
        receipt = json.loads((self.store.work / "checkpoint.json").read_text())
        self.assertEqual(len(receipt["completed"]), 11)
        self.assertEqual(receipt["pending"], [])
        self.payloads.clear()
        self.run_pipeline(self.new_engine())
        self.assertFalse(self.payloads)
        self.assertTrue(all("body" not in page for page in self.engine.seen.values()))

    def test_failed_summary_resumes_completed_targets(self):
        source = self.store.load(SOURCE_MANUAL)
        source["records"]["second"] = {"title": "Second retirement", "urls": ["https://example.com/second"]}
        self.fetch.bodies["https://example.com/second"] = "<main>Second</main>"
        self.store.save(SOURCE_MANUAL)
        self.engine.download()

        def fail_second(payload):
            if payload.get("id") == "second":
                raise ValueError("Model temporarily unavailable")
            return self.summarize(payload)

        self.engine.summarizer = fail_second
        with self.assertRaisesRegex(ValueError, "1 targets blocked"):
            self.engine.enrich()
        self.assertIn("manual-id", self.store.load(ENRICH_AUTO)["records"])
        self.payloads.clear()
        self.new_engine().enrich()
        aggregate_ids = [payload["id"] for payload in self.payloads if payload["kind"] == "retirement"]
        self.assertEqual(aggregate_ids, ["second"])

    def test_summary_seal_detects_edits_and_reprocessing_repairs_it(self):
        output = self.run_pipeline()
        automatic = self.store.load(ENRICH_AUTO)
        automatic["records"]["manual-id"]["summary"] = "Unprocessed edit"
        self.store.save(ENRICH_AUTO)
        with self.assertRaisesRegex(ValueError, "changed outside processing"):
            merge(self.store, output)
        self.new_engine().enrich()
        merge(self.store, output)

    def test_download_progress_is_saved_before_later_batch_failure(self):
        source = self.store.load(SOURCE_MANUAL)
        for index in range(10):
            url = f"https://example.com/batch-{index}"
            source["records"][f"batch-{index}"] = {"title": f"Batch {index}", "urls": [url]}
            self.fetch.bodies[url] = f"<main>Batch {index}</main>"
        self.store.save(SOURCE_MANUAL)
        self.fetch.failures.add("https://example.com/batch-9")
        with self.assertRaisesRegex(ValueError, "source downloads failed"):
            self.engine.download()
        disk = json.loads((self.directory / f"{SOURCE_MANUAL}.json").read_text(encoding="utf-8"))
        self.assertEqual(len(disk["pages"]), 11)
        receipt = json.loads((self.store.work / "checkpoint.json").read_text())
        self.assertEqual(len(receipt["completed"]), 10)
        self.assertEqual(receipt["failed"][0]["id"], "batch-9")

    def test_stop_request_keeps_stages_intact_and_resume_works(self):
        (self.store.work / "stop").touch()
        with self.assertRaisesRegex(ValueError, "Stop requested"):
            self.engine.download()
        (self.store.work / "stop").unlink()
        self.run_pipeline()

    def test_legacy_refresh_refuses_new_catalog_without_network(self):
        output = self.run_pipeline()
        original = output.read_bytes()
        with self.assertRaisesRegex(ValueError, "JSON enrichment"):
            refresh_catalog(fetcher=lambda _: self.fail("Legacy refresh must not fetch"), output=output)
        self.assertEqual(output.read_bytes(), original)

    def test_many_response_bodies_are_limited_to_active_workers(self):
        class Body(bytes):
            live = 0
            peak = 0
            guard = threading.Lock()

            def __new__(cls):
                result = super().__new__(cls, b"Retirement information. " * 8192)
                with cls.guard:
                    cls.live += 1
                    cls.peak = max(cls.peak, cls.live)
                return result

            def __del__(self):
                with type(self).guard:
                    type(self).live -= 1

        pages = {}

        def fetch(url, previous, force):
            return {"status": 200, "body": Body(), "headers": {"Content-Type": "text/plain"}}

        engine = self.new_engine(workers=3)
        engine.fetcher = fetch
        engine.refresh_pages([f"https://example.com/body-{index}" for index in range(25)], pages)
        self.assertEqual(Body.live, 0)
        self.assertLessEqual(Body.peak, 3)
        self.assertEqual(len(pages), 25)
        self.assertTrue(all("body" not in entry for entry in engine.seen.values()))

    def test_absent_hidden_and_legacy_manual_records_are_preserved(self):
        baseline = catalog()
        protected = copy.deepcopy(baseline["records"][0])
        protected["id"] = "manual-id"
        protected["hidden"] = True
        baseline["records"].append(protected)
        output = self.directory / "retirements.json"
        write_json(output, baseline, None)
        self.run_pipeline()
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["records"], baseline["records"])

    def test_mutated_stage_does_not_overwrite_user_changes(self):
        path = self.directory / f"{SOURCE_MANUAL}.json"
        data = json.loads(path.read_text())
        data["records"]["manual-id"]["title"] = "User editing"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed during processing"):
            self.store.save(SOURCE_MANUAL)
        self.assertEqual(json.loads(path.read_text())["records"]["manual-id"]["title"], "User editing")

    def test_duplicate_url_ids_and_missing_downloads_fail(self):
        stage = self.store.load(SOURCE_MANUAL)
        stage["records"]["second"] = {"title": "Second", "urls": [ROOT_URL + "#fragment"]}
        self.store.save(SOURCE_MANUAL)
        with self.assertRaisesRegex(ValueError, "multiple IDs"):
            self.engine.download()
        del stage["records"]["second"]
        self.store.save(SOURCE_MANUAL)
        with self.assertRaisesRegex(ValueError, "Download all"):
            self.engine.enrich()

    def test_azure_updates_uses_exact_item_not_generic_listing(self):
        stage = self.store.load(SOURCE_MANUAL)
        stage["records"] = {"a": {"title": ITEM["title"], "urls": ["https://azure.microsoft.com/updates?id=a"]}}
        self.store.save(SOURCE_MANUAL)
        api = "https://www.microsoft.com/releasecommunications/api/v2/azure/a"
        calls = []

        def fetch(url, previous, force):
            calls.append(url)
            return {"status": 200, "body": json.dumps(ITEM).encode(), "headers": {"Content-Type": "application/json"}}

        engine = self.new_engine()
        engine.fetcher = fetch
        engine.download()
        self.assertEqual(calls, [api])
        self.assertIn("a", stage["records"])

    def test_exact_api_identity_mismatch_fails(self):
        with self.assertRaisesRegex(DownloadError, "exact retirement"):
            extract_content(json.dumps(ITEM).encode(), "application/json", ROOT_URL, "different")

    def test_discovery_only_azure_updates_preserves_absent_source_entries(self):
        stage = self.store.load(SOURCE_AUTO)
        stage["records"]["old"] = {"title": "Old retirement", "urls": ["https://example.com/old"]}
        self.store.save(SOURCE_AUTO)
        urls = []

        def fetch(url, previous, force):
            urls.append(url)
            return {"status": 200, "body": json.dumps({"@odata.count": 1, "value": [ITEM]}).encode()}

        discover(self.store, fetch)
        self.assertEqual(len(urls), 1)
        self.assertIn("releasecommunications/api/v2/azure?", urls[0])
        self.assertFalse(stage["records"]["old"]["present"])
        self.assertTrue(stage["records"]["a"]["present"])

    def test_blob_tampering_blocks_processing(self):
        self.engine.download()
        page = self.store.load(SOURCE_MANUAL)["pages"][ROOT_URL]
        self.store.blob(page["contentSha256"]).write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "targets blocked"):
            self.engine.enrich()


class EnrichmentBoundaries(unittest.TestCase):
    def test_formatting_without_answer_content_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "only formatting"):
            format_answer("###")

    def test_rich_answer_escapes_raw_html_and_does_not_create_active_links_or_attributes(self):
        text = (
            '# Scope\n\n<script>alert("unsafe")</script>\n'
            '<img src=x onerror=unsafe>\n\n'
            '[Bad](javascript:alert)\n\n![Image](https://example.com/image)\n\n'
            '```html onclick=unsafe\n<div onclick="unsafe">example & text</div>\n```\n\n'
            '3. Third step\n4. Fourth step'
        )
        plain, rich = format_answer(text)
        fragment = parseFragment(rich, namespaceHTMLElements=False)
        self.assertTrue(valid_question_html(rich))
        self.assertIsNotNone(fragment.find("h3"))
        self.assertIsNotNone(fragment.find("ol/li"))
        self.assertIsNone(fragment.find(".//script"))
        self.assertIsNone(fragment.find(".//img"))
        self.assertIsNone(fragment.find(".//a"))
        self.assertTrue(all(not node.attrib for node in fragment.iter()))
        self.assertIn('<div onclick="unsafe">example & text</div>', plain)
        self.assertIn('<div onclick="unsafe">example & text</div>', fragment.find("pre/code").text)

    def test_http_error_responses_close_after_unchanged_or_failed_download(self):
        for code in (304, 404):
            with self.subTest(code=code):
                body = io.BytesIO()
                opener = Mock()
                opener.open.side_effect = HTTPError(ROOT_URL, code, "response", {}, body)
                with patch("scripts.enrichment_http.public_url", side_effect=lambda url, **_: url), \
                        patch("scripts.enrichment_http.build_opener", return_value=opener):
                    if code == 304:
                        self.assertEqual(fetch_http(ROOT_URL)["status"], 304)
                    else:
                        with self.assertRaises(DownloadError):
                            fetch_http(ROOT_URL)
                self.assertTrue(body.closed)

    def test_url_safety_and_fragment_identity(self):
        self.assertEqual(public_url("https://example.com/a?q=1#heading"), "https://example.com/a?q=1")
        for url in ("http://example.com", "https://127.0.0.1/a", "https://user:pass@example.com",
                    "https://localhost/a", "https://[::1]/a", "https://example.com:8080/a"):
            with self.subTest(url=url), self.assertRaises(DownloadError):
                public_url(url)
        with patch("scripts.enrichment_http.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("10.0.0.1", 443)),
        ]), self.assertRaises(DownloadError):
            public_url("https://example.com", resolve=True)

    def test_summary_schema_and_deadline_validation(self):
        invalid = summary()
        invalid["questions"].pop("impact")
        with self.assertRaises(ValueError):
            valid_summary(invalid)
        invalid = summary()
        invalid["deadline"]["date"] = "2027-02-30"
        with self.assertRaises(ValueError):
            valid_summary(invalid)

    def test_cross_process_lease_and_atomic_write_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            with Stages(directory):
                with self.assertRaisesRegex(ValueError, "writer lease"):
                    with Stages(directory):
                        pass
            path = Path(directory) / "stage.json"
            write_json(path, {"a": 1}, None)
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "Concurrent change"):
                write_json(path, {"a": 2}, None)
            self.assertEqual(path.read_bytes(), before)

    def test_local_adapter_contract_and_missing_model_error(self):
        adapter = command_adapter([sys.executable, "-c", "import json,sys; print(json.dumps({'seen':json.load(sys.stdin)['kind']}))"])
        self.assertEqual(adapter({"kind": "page"}), {"seen": "page"})
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main(["run", "--data-dir", directory]), 1)
            self.assertFalse((Path(directory) / "retirements.json").exists())


if __name__ == "__main__":
    unittest.main()
