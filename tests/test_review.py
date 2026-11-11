import copy
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import catalog
from scripts.catalog import ROOT, QUESTIONS, learn_documentation_url, microsoft_techcommunity_url, parse_catalog
from scripts.feed import merge_retirements
from scripts.refresh_data import read_snapshot
from scripts.review_data import apply_reviews, main, review_report


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "retirements.json"
        self.original = catalog()
        self.output.write_text(json.dumps(self.original), encoding="utf-8")
        self.url = "https://learn.microsoft.com/en-us/azure/example/retirement"
        self.techcommunity_url = "https://techcommunity.microsoft.com/blog/azure/retirement-announcement/123456"

    def batch(self):
        record = self.original["records"][0]
        return {
            "catalogSha256": hashlib.sha256(self.output.read_bytes()).hexdigest(),
            "reviews": [{
                "id": record["id"], "summary": "Source-backed summary.",
                "questions": {section: {"introduction": "Reviewed answer."} for section in QUESTIONS},
                "sourceReview": {
                    "reviewedOn": "2026-11-11", "status": "enriched", "issues": [],
                    "deadlineSource": self.url,
                    "sources": [{"title": "Learn source", "url": self.url, "sections": list(QUESTIONS), "note": "Scope and explicit deadline."}],
                    "resourceChecks": [
                        {"url": resource["url"], "resolvedUrl": None, "status": "not-evidence", "detail": "Generic support link."}
                        for resource in record["questions"]["actions"]["resources"]
                    ],
                },
            }],
        }

    def announcement_batch(self, url):
        batch = self.batch()
        review = batch["reviews"][0]
        review["questions"]["deadline"]["date"] = "2029-01-02"
        review["sourceReview"]["deadlineSource"] = url
        review["sourceReview"]["sources"] = [{
            "title": "Azure Updates announcement", "url": url, "sections": list(QUESTIONS),
            "note": "The announcement describes the retirement and its deadline.",
        }]
        return batch

    def test_apply_preserves_feed_metadata_original_evidence_and_unrelated_records(self):
        batch = self.batch()
        batch["reviews"][0]["questions"]["deadline"]["date"] = "2029-01-02"
        result = apply_reviews(batch, self.output)
        record = result["records"][0]
        old = self.original["records"][0]
        self.assertTrue(record["manuallyEnriched"])
        self.assertEqual(record["questions"]["deadline"]["date"], "2029-01-02")
        self.assertEqual(record["sourceReview"]["deadlineSource"], self.url)
        self.assertEqual(record["sourceReview"]["originalAnnouncement"], old["questions"]["what"]["announcement"])
        self.assertEqual(record["sourceReview"]["originalDeadline"]["date"], old["questions"]["deadline"]["date"])
        for field in ("id", "title", "sourceUrl", "services", "categories", "announcedOn", "lastUpdatedOn"):
            self.assertEqual(record[field], old[field])
        self.assertEqual(result["retrievedAt"], self.original["retrievedAt"])
        self.assertEqual(result["records"][1:], self.original["records"][1:])
        self.assertEqual(merge_retirements(self.original["records"], result["records"])[0], record)
        self.assertEqual(json.loads(self.output.read_bytes()), result)
        self.assertEqual(list(self.output.parent.glob("*.tmp")), [])

    def test_apply_accepts_safe_question_html(self):
        batch = self.batch()
        markup = "<p>Formatted <strong>answer</strong>.</p>"
        batch["reviews"][0]["questions"]["what"]["html"] = markup
        result = apply_reviews(batch, self.output)
        self.assertEqual(result["records"][0]["questions"]["what"]["html"], markup)

    def test_repeat_review_preserves_first_announcement_and_deadline(self):
        initial = self.batch()
        initial["reviews"][0]["sourceReview"]["guidanceSource"] = self.url
        first = apply_reviews(initial, self.output)
        self.original = copy.deepcopy(first)
        batch = self.batch()
        batch["reviews"][0]["questions"]["what"]["announcement"] = "New professional summary."
        second = apply_reviews(batch, self.output)
        self.assertEqual(second["records"][0]["sourceReview"]["originalAnnouncement"],
                         first["records"][0]["sourceReview"]["originalAnnouncement"])
        self.assertEqual(second["records"][0]["sourceReview"]["originalDeadline"],
                         first["records"][0]["sourceReview"]["originalDeadline"])
        self.assertEqual(second["records"][0]["sourceReview"]["guidanceSource"], self.url)
        self.original = copy.deepcopy(second)
        batch = self.batch()
        batch["reviews"][0]["sourceReview"]["guidanceSource"] = None
        third = apply_reviews(batch, self.output)
        self.assertIsNone(third["records"][0]["sourceReview"]["guidanceSource"])

    def test_invalid_or_stale_batches_never_write(self):
        original = self.output.read_bytes()
        cases = []
        batch = self.batch()
        batch["catalogSha256"] = "stale"
        cases.append(batch)
        batch = self.batch()
        batch["reviews"] *= 2
        cases.append(batch)
        batch = self.batch()
        del batch["reviews"][0]["questions"]["progress"]
        cases.append(batch)
        batch = self.batch()
        batch["reviews"][0]["questions"]["what"]["question"] = "Changed heading"
        cases.append(batch)
        batch = self.batch()
        batch["reviews"][0]["sourceReview"]["originalAnnouncement"] = "Fabricated"
        cases.append(batch)
        batch = self.batch()
        batch["reviews"][0]["sourceReview"]["resourceChecks"] = []
        if self.original["records"][0]["questions"]["actions"]["resources"]:
            cases.append(batch)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply_reviews(value, self.output)
            self.assertEqual(self.output.read_bytes(), original)

    def test_review_validation_requires_evidence_and_rejects_untrusted_sources(self):
        value = apply_reviews(self.batch(), self.output)
        cases = [
            {"reviewedOn": None}, {"reviewedOn": "2026-02-30"}, {"status": "verified"},
            {"sources": []}, {"sources": [{"title": "Q&A", "url": "https://learn.microsoft.com/en-us/answers/questions/1", "sections": list(QUESTIONS), "note": "Community answer"}]},
            {"deadlineSource": "https://example.com/date"}, {"originalDeadline": {}},
            {"status": "needs-review", "issues": []},
            {"guidanceSource": "https://azure.microsoft.com/updates"},
            {"guidanceSource": "https://learn.microsoft.com/en-us/azure/other"},
            {"guidanceSource": "https://learn.microsoft.com/en-us/answers/questions/1"},
            {"guidanceSource": "https://techcommunity.microsoft.com/blog/azure/retirement"},
        ]
        for changes in cases:
            invalid = copy.deepcopy(value)
            invalid["records"][0]["sourceReview"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_catalog(invalid)
        invalid = copy.deepcopy(value)
        invalid["records"][0]["questions"]["deadline"]["date"] = "2029-01-02"
        invalid["records"][0]["sourceReview"]["deadlineSource"] = None
        with self.assertRaises(ValueError):
            parse_catalog(invalid)
        invalid = copy.deepcopy(value)
        invalid["records"][0]["sourceReview"]["guidanceSource"] = self.url
        invalid["records"][0]["sourceReview"]["sources"][0]["sections"].remove("actions")
        invalid["records"][0]["sourceReview"]["sources"].append({
            "title": "Other source", "url": "https://learn.microsoft.com/en-us/azure/other",
            "sections": ["actions"], "note": "Action coverage."
        })
        with self.assertRaises(ValueError):
            parse_catalog(invalid)
        for url in ("https://learn.microsoft.com/en-us/answers/", "https://learn.microsoft.com/answers/",
                    "https://learn.microsoft.com/en-us/training/", "https://learn.microsoft.com.evil.test/azure/",
                    "https://name@learn.microsoft.com/azure/", "http://learn.microsoft.com/azure/"):
            self.assertFalse(learn_documentation_url(url))
        self.assertTrue(learn_documentation_url(self.url))
        for url in (
            "https://techcommunity.microsoft.com.evil.test/blog/azure/retirement-announcement/123456",
            "https://name@techcommunity.microsoft.com/blog/azure/retirement-announcement/123456",
            "http://techcommunity.microsoft.com/blog/azure/retirement-announcement/123456",
            "https://techcommunity.microsoft.com/",
            "https://techcommunity.microsoft.com/discussions/azure/retirement",
            "https://techcommunity.microsoft.com/t5/user/viewprofilepage/user-id/123",
            "https://techcommunity.microsoft.com/blog/azure/retirement-announcement",
            "https://techcommunity.microsoft.com/blog/azure/",
            "https://techcommunity.microsoft.com/t5/azure-blog/retirement-announcement",
        ):
            self.assertFalse(microsoft_techcommunity_url(url))
        self.assertTrue(microsoft_techcommunity_url(self.techcommunity_url))
        self.assertTrue(microsoft_techcommunity_url(
            "https://techcommunity.microsoft.com/t5/azure-sql-blog/change-hardware-generation/ba-p/699824"
        ))

    def test_verified_techcommunity_article_can_support_retirement_and_deadline(self):
        techcommunity_url = self.techcommunity_url
        batch = self.batch()
        batch["reviews"][0]["questions"]["deadline"]["date"] = "2029-01-02"
        batch["reviews"][0]["sourceReview"]["deadlineSource"] = techcommunity_url
        batch["reviews"][0]["sourceReview"]["sources"] = [{
            "title": "Azure retirement announcement",
            "url": techcommunity_url,
            "sections": list(QUESTIONS),
            "note": "The Microsoft product-team post describes the affected scope, deadline, and migration guidance.",
        }]
        result = apply_reviews(batch, self.output)
        self.assertEqual(result["records"][0]["sourceReview"]["deadlineSource"], techcommunity_url)

    def test_announcement_title_or_description_can_support_reviewed_deadline(self):
        for location, url in (
            ("title", "https://azure.microsoft.com/updates?id=a"),
            ("description", "https://azure.microsoft.com/en-us/updates?id=a"),
        ):
            with self.subTest(location=location):
                self.original = catalog()
                record = self.original["records"][0]
                record["title"] = "API keys retire on 2 January 2029" if location == "title" else "API keys retire"
                record["questions"]["what"]["announcement"] = (
                    "API keys retire on 2 January 2029." if location == "description" else "API keys are retiring."
                )
                record["questions"]["deadline"].update({"date": None, "month": None})
                self.output.write_text(json.dumps(self.original), encoding="utf-8")
                result = apply_reviews(self.announcement_batch(url), self.output)
                reviewed = result["records"][0]
                self.assertEqual(reviewed["questions"]["deadline"]["date"], "2029-01-02")
                self.assertEqual(reviewed["sourceReview"]["deadlineSource"], url)
                self.assertIsNone(reviewed["sourceReview"]["originalDeadline"]["date"])
                self.assertEqual(reviewed["sourceReview"]["originalAnnouncement"], record["questions"]["what"]["announcement"])

    def test_announcement_deadline_requires_matching_official_record_and_citation(self):
        original = self.output.read_bytes()
        for url in (
            "https://azure.microsoft.com/en-us/updates?id=other",
            "https://azure.microsoft.com.evil.test/en-us/updates?id=a",
            "https://azure.microsoft.com@evil.test/en-us/updates?id=a",
            "https://name@azure.microsoft.com/en-us/updates?id=a",
            "http://azure.microsoft.com/en-us/updates?id=a",
            "https://azure.microsoft.com:8443/en-us/updates?id=a",
            "https://azure.microsoft.com:invalid/en-us/updates?id=a",
            "https://azure.microsoft.com/en-us/updates?id=a&id=a",
            "https://azure.microsoft.com/en-us/updates",
            "https://azure.microsoft.com/en-us/updates/other?id=a",
        ):
            batch = self.batch()
            review = batch["reviews"][0]
            review["questions"]["deadline"]["date"] = "2029-01-02"
            review["sourceReview"]["deadlineSource"] = url
            review["sourceReview"]["sources"].append({
                "title": "Claimed announcement", "url": url, "sections": ["deadline"], "note": "Claimed deadline.",
            })
            with self.subTest(url=url), self.assertRaises(ValueError):
                apply_reviews(batch, self.output)
            self.assertEqual(self.output.read_bytes(), original)
        url = self.original["records"][0]["sourceUrl"]
        batch = self.batch()
        review = batch["reviews"][0]
        review["questions"]["deadline"]["date"] = "2029-01-02"
        review["sourceReview"]["deadlineSource"] = url
        review["sourceReview"]["sources"].append({
            "title": "Announcement", "url": url, "sections": ["what"], "note": "Announcement scope.",
        })
        with self.assertRaises(ValueError):
            apply_reviews(batch, self.output)
        self.assertEqual(self.output.read_bytes(), original)

    def test_announcement_does_not_expand_guidance_or_tracking_sources(self):
        url = self.original["records"][0]["sourceUrl"]
        value = apply_reviews(self.announcement_batch(url), self.output)
        invalid = copy.deepcopy(value)
        invalid["records"][0]["sourceReview"]["guidanceSource"] = url
        with self.assertRaises(ValueError):
            parse_catalog(invalid)
        invalid = copy.deepcopy(value)
        invalid["records"][0]["questions"]["progress"]["tracking"] = {
            "guidance": "Inspect the affected resources.", "sourceUrl": url,
        }
        with self.assertRaises(ValueError):
            parse_catalog(invalid)
        invalid = copy.deepcopy(value)
        invalid["records"][0]["sourceUrl"] = "https://azure.microsoft.com/updates?id=another-record"
        with self.assertRaises(ValueError):
            parse_catalog(invalid)

    @unittest.skipUnless(shutil.which("node"), "Node.js is optional")
    def test_browser_and_python_agree_on_announcement_deadline_sources(self):
        url = "https://azure.microsoft.com/en-us/updates?id=a"
        valid = apply_reviews(self.announcement_batch(url), self.output)
        cases = [valid]
        for source in (
            self.original["records"][0]["sourceUrl"],
            "https://azure.microsoft.com/en-us/updates?id=other",
            "https://azure.microsoft.com.evil.test/en-us/updates?id=a",
            "https://name@azure.microsoft.com/en-us/updates?id=a",
            "https://azure.microsoft.com:8443/en-us/updates?id=a",
            "https://azure.microsoft.com/en-us/updates?id=a&id=a",
        ):
            case = copy.deepcopy(valid)
            case["records"][0]["sourceReview"]["deadlineSource"] = source
            case["records"][0]["sourceReview"]["sources"][0]["url"] = source
            cases.append(case)
        invalid = copy.deepcopy(valid)
        invalid["records"][0]["sourceUrl"] = "https://azure.microsoft.com/updates?id=other"
        cases.append(invalid)
        invalid = copy.deepcopy(valid)
        invalid["records"][0]["sourceReview"]["sources"][0]["sections"].remove("deadline")
        invalid["records"][0]["sourceReview"]["sources"].append({
            "title": "Learn source", "url": self.url, "sections": ["deadline"], "note": "Other deadline evidence.",
        })
        cases.append(invalid)
        invalid = copy.deepcopy(valid)
        invalid["records"][0]["questions"]["progress"]["tracking"] = {"guidance": "Inspect resources.", "sourceUrl": url}
        cases.append(invalid)
        expected = [True, True, False, False, False, False, False, False, False, False]
        python_results = []
        for case in cases:
            try:
                parse_catalog(case)
                python_results.append(True)
            except ValueError:
                python_results.append(False)
        self.assertEqual(python_results, expected)
        module = (ROOT / "site" / "assets" / "js" / "catalog.js").as_uri()
        program = f"""
            import {{ readFile }} from 'node:fs/promises';
            const source = await readFile(new URL({json.dumps(module)}), 'utf8');
            const {{ parseCatalog }} = await import(
                `data:text/javascript;base64,${{Buffer.from(source).toString('base64')}}`
            );
            let input = '';
            for await (const chunk of process.stdin) input += chunk;
            const results = JSON.parse(input).map(catalog => {{
                try {{ parseCatalog(catalog); return true; }} catch {{ return false; }}
            }});
            console.log(JSON.stringify(results));
        """
        result = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", program],
            input=json.dumps(cases), text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected)

    def test_tracking_requires_a_cited_authoritative_source_covering_progress_and_can_be_cleared(self):
        batch = self.batch()
        batch["reviews"][0]["questions"]["progress"]["tracking"] = {
            "guidance": "Inspect the affected resources.", "sourceUrl": self.url,
        }
        value = apply_reviews(batch, self.output)
        tracking = value["records"][0]["questions"]["progress"]["tracking"]
        self.assertEqual(tracking["sourceUrl"], self.url)
        for replacement in (
            {"guidance": "", "sourceUrl": self.url},
            {"guidance": "Inspect resources.", "sourceUrl": "https://example.com/"},
            {"guidance": "Inspect resources.", "sourceUrl": "https://learn.microsoft.com/en-us/azure/other"},
            {"guidance": "Inspect resources.", "sourceUrl": self.url, "extra": True},
            "invalid",
        ):
            invalid = copy.deepcopy(value)
            invalid["records"][0]["questions"]["progress"]["tracking"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                parse_catalog(invalid)
        invalid = copy.deepcopy(value)
        invalid["records"][0]["sourceReview"]["sources"][0]["sections"].remove("progress")
        invalid["records"][0]["sourceReview"]["sources"].append({
            "title": "Other source", "url": "https://learn.microsoft.com/en-us/azure/other",
            "sections": ["progress"], "note": "Other progress coverage.",
        })
        with self.assertRaises(ValueError):
            parse_catalog(invalid)
        techcommunity_url = self.techcommunity_url
        batch = self.batch()
        batch["reviews"][0]["questions"]["progress"]["tracking"] = {
            "guidance": "Inventory the affected resources.", "sourceUrl": techcommunity_url,
        }
        batch["reviews"][0]["sourceReview"]["sources"] = [{
            "title": "Azure retirement announcement",
            "url": techcommunity_url,
            "sections": list(QUESTIONS),
            "note": "The Microsoft product-team post gives resource inventory and migration guidance.",
        }]
        batch["reviews"][0]["sourceReview"]["deadlineSource"] = techcommunity_url
        tracked = apply_reviews(batch, self.output)
        self.assertEqual(tracked["records"][0]["questions"]["progress"]["tracking"]["sourceUrl"], techcommunity_url)
        invalid = copy.deepcopy(value)
        del invalid["records"][0]["sourceReview"]
        with self.assertRaises(ValueError):
            parse_catalog(invalid)
        self.original = copy.deepcopy(value)
        batch = self.batch()
        batch["reviews"][0]["questions"]["progress"]["tracking"] = None
        cleared = apply_reviews(batch, self.output)
        self.assertIsNone(cleared["records"][0]["questions"]["progress"]["tracking"])

    def test_excluded_references_require_confirmed_gone_and_are_preserved(self):
        batch = self.batch()
        batch["reviews"][0]["sourceReview"]["excludedReferences"] = [
            {"url": self.url, "checkedOn": "2026-11-11", "httpStatus": 404}
        ]
        value = apply_reviews(batch, self.output)
        for change in (
            {"url": "https://example.com/unknown"},
            {"checkedOn": "2026-02-30"},
            {"httpStatus": 403},
            {"httpStatus": True},
        ):
            invalid = copy.deepcopy(value)
            invalid["records"][0]["sourceReview"]["excludedReferences"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_catalog(invalid)
        self.original = copy.deepcopy(value)
        second = apply_reviews(self.batch(), self.output)
        self.assertEqual(second["records"][0]["sourceReview"]["excludedReferences"],
                         value["records"][0]["sourceReview"]["excludedReferences"])

    def test_concurrent_publish_preserves_external_content(self):
        batch = self.batch()
        external = b"Concurrent external edit"
        calls = 0
        def read(output):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.output.write_bytes(external)
            return read_snapshot(output)
        with patch("scripts.review_data.read_snapshot", side_effect=read), patch("scripts.refresh_data.read_snapshot", side_effect=read):
            with self.assertRaisesRegex(ValueError, "changed during content review"):
                apply_reviews(batch, self.output)
        self.assertEqual(self.output.read_bytes(), external)
        self.assertEqual(list(self.output.parent.glob("*.tmp")), [])

    def test_report_resumes_and_preserves_manual_only_records(self):
        value = self.original
        record = copy.deepcopy(value["records"][0])
        record["id"] = "manual"
        record["manuallyEnriched"] = True
        record["customNotes"] = {"owner": "Platform team"}
        value["records"].append(record)
        self.output.write_text(json.dumps(value), encoding="utf-8")
        report = review_report(value, 10)
        self.assertEqual(report["manualOnly"], 1)
        self.assertIn("manual", [item["id"] for item in report["next"]])
        batch = self.batch()
        batch["reviews"][0]["id"] = "manual"
        batch["reviews"][0]["summary"] = record["summary"]
        batch["reviews"][0]["questions"] = {section: {} for section in QUESTIONS}
        unsafe_batch = copy.deepcopy(batch)
        unsafe_batch["reviews"][0]["summary"] = "Overwrite custom summary."
        with self.assertRaisesRegex(ValueError, "preserve its summary"):
            apply_reviews(unsafe_batch, self.output)
        unsafe_batch = copy.deepcopy(batch)
        unsafe_batch["reviews"][0]["questions"]["what"]["announcement"] = "Overwrite manual answer."
        with self.assertRaisesRegex(ValueError, "preserve its answers"):
            apply_reviews(unsafe_batch, self.output)
        # Apply the metadata-only batch to the manual record without replacing its content.
        reviewed = apply_reviews(batch, self.output)
        manual = next(item for item in reviewed["records"] if item["id"] == "manual")
        self.assertEqual(manual["summary"], record["summary"])
        self.assertEqual(manual["questions"], record["questions"])
        self.assertEqual(manual["customNotes"], record["customNotes"])
        self.assertEqual(manual["sourceReview"]["status"], "enriched")
        report = review_report(reviewed, 10)
        self.assertEqual(report["reviewed"], 1)
        self.assertEqual(report["enriched"], 1)
        self.assertEqual(report["manualOnly"], 0)
        self.assertEqual({item["id"] for item in report["next"]}, {"a", "manual"})
        for limit in (0, -1, True):
            with self.assertRaises(ValueError):
                review_report(reviewed, limit)

    def test_report_hash_always_identifies_the_reported_snapshot(self):
        root = Path(self.temporary.name)
        path = root / "data" / "retirements.json"
        path.parent.mkdir()
        original = self.output.read_bytes()
        path.write_bytes(original)
        def concurrent_report(value, limit):
            external = copy.deepcopy(value)
            external["source"] = "https://example.com/changed-source"
            path.write_text(json.dumps(external), encoding="utf-8")
            return review_report(value, limit)
        output = io.StringIO()
        with patch("scripts.review_data.ROOT", root), patch("sys.argv", ["review_data"]), \
                patch("scripts.review_data.review_report", side_effect=concurrent_report), patch("sys.stdout", output):
            main()
        report = json.loads(output.getvalue())
        self.assertEqual(report["catalogSha256"], hashlib.sha256(original).hexdigest())
        self.assertNotEqual(report["catalogSha256"], hashlib.sha256(path.read_bytes()).hexdigest())
