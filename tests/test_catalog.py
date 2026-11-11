import copy
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import ITEM, catalog
from scripts.catalog import (
    ROOT, QUESTIONS, DETAIL_QUESTIONS, categories_of, countdown, days_until, format_date, group_retirements,
    parse_catalog, prepare_site, record_url, retirement_year, safe_url, status_of,
    group_timeline, in_retirement_window, retirement_outlook, retirement_window, services_of, sort_timeline,
)
from scripts.feed import normalize, title_date


class CatalogTests(unittest.TestCase):
    def test_hidden_records_remain_directly_available_but_not_in_navigation_counts(self):
        value = catalog()
        hidden = copy.deepcopy(value["records"][0])
        hidden.update({"id": "hidden", "title": "Hidden retirement", "hidden": True, "categories": ["Hidden category"]})
        value["records"].append(hidden)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "data" / "retirements.json"
            source.parent.mkdir()
            source.write_text(json.dumps(value), encoding="utf-8")
            metadata = prepare_site(root, "2026-11-10")
            self.assertIn("hidden", metadata["byId"])
            self.assertNotIn("hidden", metadata["initialIds"])
            self.assertNotIn("Hidden category", metadata["categories"])
            self.assertEqual(metadata["count"], len(value["records"]) - 1)
            self.assertNotIn("hidden", [entry["id"] for year in metadata["navigation"]
                                        for category in year["categories"] for entry in category["records"]])
            self.assertEqual(json.loads((root / "site" / "assets" / "data" / "retirements.json").read_text(encoding="utf-8")), value)
        for bad in (None, "true", 1, []):
            invalid = copy.deepcopy(value)
            invalid["records"][-1]["hidden"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_catalog(invalid)

    def test_timeline_groups_categories_and_individual_services_with_descending_deadlines(self):
        def record(identifier, title, deadline, categories, services):
            return {
                "id": identifier, "title": title, "categories": categories,
                "service": "Combined services", "services": services,
                "questions": {"deadline": {"date": deadline, "month": "May 2029"}},
            }
        records = [
            record("a", "Zulu", "2028-01-01", ["Compute"], ["VM"]),
            record("b", "Earlier", "2026-01-01", ["Compute"], ["VM"]),
            record("c", "Unconfirmed", None, ["Compute"], ["VM"]),
            record("d", "Alpha", "2028-01-01", ["Compute"], ["VM"]),
            record("e", "Multiple services", "2027-01-01", ["Storage", "Compute", "Storage"], ["VM", "Blob", "VM"]),
        ]
        before = copy.deepcopy(records)
        groups = group_timeline(records)
        self.assertEqual([group["name"] for group in groups], ["Compute", "Storage"])
        self.assertEqual([group["count"] for group in groups], [5, 1])
        self.assertEqual([group["name"] for group in groups[0]["services"]], ["Blob", "VM"])
        self.assertEqual([record["id"] for record in groups[0]["services"][1]["records"]], ["d", "a", "e", "b", "c"])
        self.assertEqual([record["id"] for record in sort_timeline(records)], ["d", "a", "e", "b", "c"])
        filtered = group_timeline(records, category="Storage", service="Blob")
        self.assertEqual(len(filtered), 1)
        self.assertEqual([group["name"] for group in filtered[0]["services"]], ["Blob"])
        self.assertEqual([record["id"] for record in filtered[0]["services"][0]["records"]], ["e"])
        self.assertEqual(group_timeline(records, service="Missing"), [])
        self.assertEqual(group_timeline([]), [])
        self.assertEqual(records, before)

    def test_timeline_keeps_uncategorized_and_primary_service_fallbacks(self):
        record = catalog()["records"][0]
        del record["categories"]
        record.update({"services": [], "service": "Azure fallback"})
        self.assertEqual(services_of(record), ["Azure fallback"])
        group = group_timeline([record])[0]
        self.assertEqual(group["name"], "Uncategorized")
        self.assertEqual(group["services"][0]["name"], "Azure fallback")

    def test_preparation_selects_latest_deadlines_instead_of_latest_announcements(self):
        value = catalog()
        original = value["records"][0]
        value["records"] = []
        for identifier, deadline, announced in (
            ("unknown", None, "2026-11-10"),
            ("earliest", "2025-01-01", "2026-11-10"),
            ("latest", "2029-01-01", "2020-01-01"),
            ("middle", "2027-01-01", "2025-01-01"),
        ):
            record = copy.deepcopy(original)
            record.update({"id": identifier, "title": identifier, "announcedOn": announced})
            record["questions"]["deadline"]["date"] = deadline
            value["records"].append(record)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "data" / "retirements.json"
            source.parent.mkdir()
            source.write_text(json.dumps(value), encoding="utf-8")
            metadata = prepare_site(root, "2026-11-10")
            self.assertEqual(metadata["initialIds"], ["latest", "middle", "earliest", "unknown"])

    def test_detail_urls_use_exact_deadlines_or_unknown_date_and_keep_unique_ids(self):
        record = catalog()["records"][0]
        for deadline, month, folder in (
            ("2026-05-12", None, "2026-05-12"),
            ("2028-02-29", None, "2028-02-29"),
            (None, "May 2027", "unknown-date"),
            (None, None, "unknown-date"),
        ):
            record["questions"]["deadline"].update({"date": deadline, "month": month})
            with self.subTest(deadline=deadline, month=month):
                self.assertEqual(record_url(record), f"/retirements/{folder}/a/")
        record["id"] = "record /?#"
        self.assertEqual(record_url(record), "/retirements/unknown-date/record%20%2F%3F%23/")

    def test_calendar_windows_cover_whole_months_and_leap_years(self):
        for today, window, expected in (
            ("2026-11-10", "6", "2027-05-31"),
            ("2026-11-10", "12", "2027-11-30"),
            ("2026-11-10", "18", "2028-05-31"),
            ("2026-11-30", "6", "2027-05-31"),
            ("2026-08-10", "6", "2027-02-28"),
            ("2026-08-31", "6", "2027-02-28"),
            ("2023-08-31", "6", "2024-02-29"),
            ("2024-02-29", "12", "2025-02-28"),
            ("2026-12-31", "6", "2027-06-30"),
            ("2026-03-31", "18", "2027-09-30"),
        ):
            with self.subTest(today=today, window=window):
                bounds = retirement_window(window, today)
                self.assertEqual(bounds["start"], today[:7] + "-01")
                self.assertEqual(bounds["end"], expected)
        with self.assertRaisesRegex(ValueError, "Unknown retirement window"):
            retirement_window("7", "2026-11-10")

    def test_outlook_is_cumulative_and_excludes_unknown_dates(self):
        dates = ["2025-12-31", "2026-01-01", "2026-10-31", "2026-11-01", "2026-11-09",
                 "2026-11-10", "2027-05-31", "2027-06-01", "2027-11-30",
                 "2027-12-01", "2028-05-31", "2028-06-01", None]
        records = [{"questions": {"deadline": {"date": value, "month": "May 2027"}}} for value in dates]
        outlook = retirement_outlook(records, "2026-11-10")
        self.assertEqual([window["key"] for window in outlook], ["retired-year", "6", "12", "18"])
        self.assertEqual([window["count"] for window in outlook], [4, 4, 6, 8])
        self.assertFalse(in_retirement_window({"date": None}, "18", "2026-11-10"))
        self.assertTrue(in_retirement_window({"date": "2026-11-10"}, "6", "2026-11-10"))
        self.assertFalse(in_retirement_window({"date": "2026-11-10"}, "retired-year", "2026-11-10"))
        self.assertTrue(in_retirement_window({"date": "2026-11-01"}, "6", "2026-11-10"))
        self.assertFalse(in_retirement_window({"date": "2026-10-31"}, "6", "2026-11-10"))

    def test_upcoming_windows_roll_at_month_boundaries_not_day_changes(self):
        first = retirement_window("6", "2026-11-01")
        for today in ("2026-11-10", "2026-11-30"):
            self.assertEqual(retirement_window("6", today), first)
        december = retirement_window("6", "2026-12-01")
        self.assertEqual(december["start"], "2026-12-01")
        self.assertEqual(december["end"], "2027-06-30")

    def test_retired_calendar_year_rolls_over_at_new_year(self):
        for value in ("2026-12-31", "2027-01-01"):
            self.assertFalse(in_retirement_window({"date": value}, "retired-year", "2027-01-01"))
        self.assertTrue(in_retirement_window({"date": "2027-01-01"}, "retired-year", "2027-01-02"))
        self.assertFalse(in_retirement_window({"date": "2026-12-31"}, "retired-year", "2027-01-02"))

    def test_nullable_fields_and_protected_older_categories(self):
        value = catalog()
        self.assertEqual(parse_catalog(value), value)
        value["records"][0]["manuallyEnriched"] = True
        del value["records"][0]["categories"]
        self.assertEqual(parse_catalog(value), value)
        self.assertEqual(categories_of(value["records"][0]), ["Uncategorized"])

    def test_invalid_metadata_and_empty_catalogs(self):
        for value in (None, [], {}, {**catalog(), "schemaVersion": 1}, {**catalog(), "source": None}, {**catalog(), "retrievedAt": "invalid"}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Invalid retirement catalog"):
                parse_catalog(value)
        with self.assertRaisesRegex(ValueError, "Empty retirement catalog"):
            parse_catalog({**catalog(), "records": []})

    def test_invalid_record_fields_and_ids(self):
        changes = [
            {"id": 1}, {"id": ""}, {"id": "."}, {"id": ".."}, {"title": None}, {"services": [42]},
            {"services": None}, {"announcedOn": "2026-13-01"}, {"lastUpdatedOn": "2026-02-30"},
            {"manuallyEnriched": "true"}, {"summary": None}, {"sourceUrl": None}, {"questions": []},
        ]
        for change in changes:
            value = catalog()
            value["records"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_catalog(value)
        for key in ("announcedOn", "lastUpdatedOn", "manuallyEnriched"):
            value = catalog()
            del value["records"][0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_catalog(value)
        value = catalog()
        value["records"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_catalog(value)

    def test_invalid_categories(self):
        for categories in (None, [], [""], [" "], [42], "Compute"):
            value = catalog()
            value["records"][0]["categories"] = categories
            with self.subTest(categories=categories), self.assertRaises(ValueError):
                parse_catalog(value)

    def test_all_five_question_sections_are_required(self):
        for section in QUESTIONS:
            for field in (None, "question", "introduction"):
                value = catalog()
                if field is None:
                    del value["records"][0]["questions"][section]
                else:
                    value["records"][0]["questions"][section][field] = None
                with self.subTest(section=section, field=field), self.assertRaises(ValueError):
                    parse_catalog(value)
        value = catalog()
        value["records"][0]["questions"]["extra"] = {}
        with self.assertRaises(ValueError):
            parse_catalog(value)

    def test_malformed_answers_dates_links_and_checklists(self):
        cases = [
            ("what", "announcement", None), ("what", "financialConsiderations", False),
            ("actions", "recommendedAction", []), ("actions", "resources", None),
            ("actions", "resources", [None]), ("actions", "resources", [{"title": "Guide", "url": 42}]),
            ("actions", "support", {}), ("actions", "supportGuidance", None),
            ("impact", "guidance", None), ("impact", "notice", None), ("impact", "advisor", None),
            ("impact", "checklist", [42]), ("deadline", "date", False), ("deadline", "date", "invalid"),
            ("deadline", "date", "2026-02-30"), ("deadline", "month", 2027),
            ("deadline", "consequences", None), ("progress", "checklist", []),
            ("progress", "checklist", [False]), ("progress", "storageNote", None),
        ]
        for section, field, invalid in cases:
            value = catalog()
            value["records"][0]["questions"][section][field] = invalid
            with self.subTest(section=section, field=field), self.assertRaises(ValueError):
                parse_catalog(value)

    def test_utc_countdown_boundaries_and_labels(self):
        for deadline, expected in (("2026-11-09", -1), ("2026-11-10", 0), ("2026-11-11", 1), ("2027-02-08", 90), ("2027-02-09", 91), (None, None)):
            with self.subTest(deadline=deadline):
                self.assertEqual(days_until({"date": deadline}, "2026-11-10"), expected)
        self.assertEqual(days_until({"date": "2028-03-01"}, "2028-02-28"), 2)
        self.assertEqual(days_until({"date": "2027-03-15"}, "2027-03-13"), 2)
        self.assertEqual(countdown({"date": "2026-11-09"}, "2026-11-10"), "Retired")
        self.assertEqual(countdown({"date": "2026-11-10"}, "2026-11-10"), "Retires today (0 days remaining)")
        self.assertEqual(countdown({"date": "2026-11-11"}, "2026-11-10"), "1 day remaining")
        self.assertEqual(countdown({"date": None}, "2026-11-10"), "Retirement date to confirm")
        self.assertEqual(status_of({"date": "2027-02-08"}, "2026-11-10"), "soon")
        self.assertEqual(status_of({"date": "2027-02-09"}, "2026-11-10"), "upcoming")
        self.assertEqual(format_date(None), "Date not specified")
        self.assertEqual(format_date("2026-11-10"), "10 Nov 2026")

    def test_safe_source_urls(self):
        for url in ("javascript:evil()", "data:text/html,test", "http://example.com", "https://[invalid"):
            self.assertIsNone(safe_url(url))
        self.assertEqual(safe_url("https://learn.microsoft.com/azure/"), "https://learn.microsoft.com/azure/")

    def test_year_category_navigation_preserves_source(self):
        records = [
            normalize({**ITEM, "id": "a", "title": "Zulu retires on 1 January 2027", "productCategories": ["Compute", "Storage", "Storage"]}),
            normalize({**ITEM, "id": "b", "title": "Alpha retirement", "productCategories": ["Storage", "Networking"]}),
            normalize({**ITEM, "id": "c", "title": "Unknown", "availabilities": []}),
            normalize({**ITEM, "id": "d", "title": "Earlier retires on 1 December 2025"}),
            normalize({**ITEM, "id": "e", "title": "Newest retires on 1 February 2028"}),
        ]
        before = copy.deepcopy(records)
        groups = group_retirements(records)
        self.assertEqual([group["year"] for group in groups], ["2028", "2027", "2025", "unknown"])
        self.assertEqual([record["id"] for record in groups[1]["records"]], ["b", "a"])
        self.assertEqual([category["name"] for category in groups[1]["categories"]], ["Compute", "Networking", "Storage"])
        self.assertEqual(len(groups[1]["categories"][2]["records"]), 2)
        self.assertEqual(retirement_year(records[1]), "2027")
        self.assertIsNone(records[1]["questions"]["deadline"]["date"])
        self.assertEqual(status_of(records[1]["questions"]["deadline"]), "unknown")
        self.assertEqual(records, before)
        self.assertEqual(group_retirements([]), [])

    def test_preparation_preserves_the_canonical_catalog_and_custom_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "data" / "retirements.json"
            source.parent.mkdir()
            value = catalog()
            record = value["records"][0]
            record["manuallyEnriched"] = True
            record["customNotes"] = {"owner": "Example team"}
            del record["categories"]
            original = json.dumps(value, indent=2).encode()
            source.write_bytes(original)
            metadata = prepare_site(root, "2026-11-10")
            self.assertEqual(metadata["byId"]["a"]["record"], record)
            self.assertEqual(metadata["byId"]["a"]["url"], record_url(record))
            self.assertEqual(metadata["byId"]["a"]["categories"], ["Uncategorized"])
            self.assertEqual(metadata["categories"], ["Uncategorized"])
            self.assertEqual([section["id"] for section in metadata["byId"]["a"]["sections"]], list(DETAIL_QUESTIONS))
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual((root / "site" / "assets" / "data" / "retirements.json").read_bytes(), original)
            self.assertFalse((root / "docs").exists())

    def test_invalid_preparation_does_not_replace_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "data" / "retirements.json"
            source.parent.mkdir()
            value = catalog()
            source.write_text(json.dumps(value), encoding="utf-8")
            prepare_site(root)
            metadata = root / "site" / "_data" / "site.json"
            before = metadata.read_bytes()
            value["records"] *= 2
            source.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare_site(root)
            self.assertEqual(metadata.read_bytes(), before)

    def test_checked_in_snapshot_has_unique_ids_and_conservative_dates(self):
        value = parse_catalog(json.loads((ROOT / "data" / "retirements.json").read_text(encoding="utf-8")))
        for record in value["records"]:
            with self.subTest(identifier=record["id"]):
                self.assertEqual(list(record["questions"]), list(QUESTIONS))
                if not record["manuallyEnriched"]:
                    self.assertEqual(record["questions"]["deadline"]["date"], title_date(record["title"]))
                    self.assertTrue(record["categories"])
                for link in record["questions"]["actions"]["resources"] + [record["questions"]["actions"]["support"], record["questions"]["impact"]["advisor"]]:
                    self.assertTrue(safe_url(link["url"]))
