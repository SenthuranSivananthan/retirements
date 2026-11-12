import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import ITEM, catalog, page
from scripts.catalog import parse_catalog
from scripts.feed import merge_retirements, normalize
from scripts.refresh_data import refresh_catalog, read_snapshot
from scripts.pipeline import Pipeline


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "retirements.json"

    def save(self, value):
        self.output.write_text(json.dumps(value), encoding="utf-8")

    def test_manual_fields_and_records_absent_from_the_feed_are_retained(self):
        baseline = catalog()
        baseline["records"].append({**copy.deepcopy(baseline["records"][0]), "id": "removed"})
        self.save(baseline)
        with Pipeline(self.output.parent / "pipeline", self.output) as pipeline:
            pipeline.seed()
            fields = {"customNotes": {"steps": ["Verify rollout"]},
                      "questions": {"actions": {"guidance": "Custom migration."}}}
            pipeline.manual({"catalogSha256": pipeline.status()["catalogSha256"],
                             "overrides": [{"id": identifier, "fields": fields} for identifier in ("a", "removed")]})
            pipeline.export()
        result = refresh_catalog(lambda url: {"@odata.count": 2, "value": [ITEM, {**ITEM, "id": "b"}]}, self.output)
        self.assertEqual([record["id"] for record in result["records"]], ["a", "b", "removed"])
        for record in (result["records"][0], result["records"][2]):
            self.assertEqual(record["questions"]["actions"]["guidance"], "Custom migration.")
            self.assertEqual(record["customNotes"], fields["customNotes"])
            self.assertNotIn("manuallyEnriched", record)
        self.assertEqual(result["records"][0]["lastUpdatedOn"], normalize(ITEM)["lastUpdatedOn"])
        self.assertEqual(merge_retirements([normalize(ITEM)], [normalize({**ITEM, "id": "old"})]), [normalize(ITEM)])

    def test_legacy_flags_and_duplicate_ids_fail(self):
        for flag in (None, "true", "false", 1):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "deprecated manual flag"):
                merge_retirements([normalize(ITEM)], [{**normalize(ITEM), "manuallyEnriched": flag}])
        with self.assertRaisesRegex(ValueError, "duplicate ID"):
            merge_retirements([normalize(ITEM)], [normalize(ITEM), normalize(ITEM)])
        with self.assertRaises(ValueError):
            merge_retirements([normalize(ITEM)], None)

    def test_initial_refresh_and_separate_manual_writer(self):
        result = refresh_catalog(page, self.output)
        self.assertNotIn("manuallyEnriched", result["records"][0])
        self.assertEqual([path.name for path in self.output.parent.iterdir()], ["retirements.json"])
        with Pipeline(self.output.parent / "pipeline", self.output) as pipeline:
            pipeline.seed()
            pipeline.manual({"catalogSha256": pipeline.status()["catalogSha256"], "overrides": [
                {"id": "a", "fields": {"questions": {"impact": {"guidance": "Custom impact."}}}},
            ]})
            pipeline.export()
        refreshed = refresh_catalog(page, self.output)
        self.assertEqual(refreshed["records"][0]["questions"]["impact"]["guidance"], "Custom impact.")
        self.assertEqual(parse_catalog(json.loads(self.output.read_text(encoding="utf-8"))), refreshed)

    def test_edits_saved_during_fetch_are_merged(self):
        self.save(catalog())
        def fetcher(url):
            current = json.loads(self.output.read_text(encoding="utf-8"))
            current["records"][0]["hidden"] = True
            self.save(current)
            return page()
        result = refresh_catalog(fetcher, self.output)
        self.assertTrue(result["records"][0]["hidden"])

    def test_missing_manual_store_preserves_the_composed_snapshot(self):
        self.save(catalog())
        with Pipeline(self.output.parent / "pipeline", self.output) as pipeline:
            pipeline.seed()
            pipeline.manual({"catalogSha256": pipeline.status()["catalogSha256"], "overrides": [
                {"id": "a", "fields": {"summary": "Manual summary."}},
            ]})
            pipeline.export()
        manual = self.output.parent / "pipeline" / "manual.sqlite"
        manual.rename(manual.with_suffix(".sqlite.backup"))
        before = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "Missing manual.sqlite"):
            refresh_catalog(page, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse(manual.exists())

    def test_bad_remote_or_local_data_cannot_replace_the_snapshot(self):
        self.save(catalog())
        before = self.output.read_bytes()
        with self.assertRaises(ValueError):
            refresh_catalog(lambda url: {"@odata.count": 1, "value": []}, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        invalid = catalog()
        invalid["records"][0]["manuallyEnriched"] = "true"
        self.save(invalid)
        before = self.output.read_bytes()
        with self.assertRaises(ValueError):
            refresh_catalog(page, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        self.output.write_text("null", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsupported catalog schema"):
            refresh_catalog(page, self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "null")

    def test_concurrent_publish_edits_are_preserved_and_temporary_files_removed(self):
        self.save(catalog())
        reads = 0
        external = None
        def read(output):
            nonlocal reads, external
            reads += 1
            if reads == 2:
                value = catalog()
                value["records"][0]["customNotes"] = "Concurrent editor."
                self.save(value)
                external = self.output.read_bytes()
            return read_snapshot(output)
        with patch("scripts.refresh_data.read_snapshot", side_effect=read):
            with self.assertRaisesRegex(ValueError, "changed during refresh"):
                refresh_catalog(page, self.output)
        self.assertEqual(self.output.read_bytes(), external)
        self.assertEqual([path.name for path in self.output.parent.iterdir()], ["retirements.json"])
