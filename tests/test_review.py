import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import catalog
from scripts.catalog import QUESTIONS, learn_documentation_url, parse_catalog
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

    def test_apply_preserves_feed_metadata_original_evidence_and_unrelated_records(self):
        batch = self.batch()
        batch["reviews"][0]["questions"]["deadline"]["date"] = "2029-01-02"
        result = apply_reviews(batch, self.output)
        record = result["records"][0]
        old = self.original["records"][0]
        self.assertTrue(record["manuallyEnriched"])
        self.assertEqual(record["sourceReview"]["originalAnnouncement"], old["questions"]["what"]["announcement"])
        self.assertEqual(record["sourceReview"]["originalDeadline"]["date"], old["questions"]["deadline"]["date"])
        for field in ("id", "title", "sourceUrl", "services", "categories", "announcedOn", "lastUpdatedOn"):
            self.assertEqual(record[field], old[field])
        self.assertEqual(result["retrievedAt"], self.original["retrievedAt"])
        self.assertEqual(result["records"][1:], self.original["records"][1:])
        self.assertEqual(merge_retirements(self.original["records"], result["records"])[0], record)
        self.assertEqual(json.loads(self.output.read_bytes()), result)
        self.assertEqual(list(self.output.parent.glob("*.tmp")), [])

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

    def test_review_validation_requires_evidence_and_rejects_community_authority(self):
        value = apply_reviews(self.batch(), self.output)
        cases = [
            {"reviewedOn": None}, {"reviewedOn": "2026-02-30"}, {"status": "verified"},
            {"sources": []}, {"sources": [{"title": "Q&A", "url": "https://learn.microsoft.com/en-us/answers/questions/1", "sections": list(QUESTIONS), "note": "Community answer"}]},
            {"deadlineSource": "https://example.com/date"}, {"originalDeadline": {}},
            {"status": "needs-review", "issues": []},
            {"guidanceSource": "https://azure.microsoft.com/updates"},
            {"guidanceSource": "https://learn.microsoft.com/en-us/azure/other"},
            {"guidanceSource": "https://learn.microsoft.com/en-us/answers/questions/1"},
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

    def test_tracking_requires_a_cited_learn_source_covering_progress_and_can_be_cleared(self):
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
        value["records"].append(record)
        self.output.write_text(json.dumps(value), encoding="utf-8")
        report = review_report(value, 10)
        self.assertEqual(report["manualOnly"], 1)
        self.assertNotIn("manual", [item["id"] for item in report["next"]])
        batch = self.batch()
        batch["reviews"][0]["id"] = "manual"
        with self.assertRaisesRegex(ValueError, "human reconciliation"):
            apply_reviews(batch, self.output)
        reviewed = apply_reviews(self.batch(), self.output)
        report = review_report(reviewed, 10)
        self.assertEqual(report["reviewed"], 1)
        self.assertEqual(report["enriched"], 1)
        self.assertEqual(report["next"][0]["id"], reviewed["records"][0]["id"])
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
