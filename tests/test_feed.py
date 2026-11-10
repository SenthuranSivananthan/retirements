import unittest
from urllib.parse import parse_qs, urlsplit

from fixtures import ITEM
from scripts.feed import fetch_retirements, normalize, read_announcement, title_date


class FeedTests(unittest.TestCase):
    def test_source_backed_dates_and_five_questions(self):
        record = normalize(ITEM)
        self.assertEqual(record["questions"]["deadline"]["date"], "2027-03-31")
        self.assertEqual(record["questions"]["deadline"]["month"], "March 2027")
        self.assertEqual(record["lastUpdatedOn"], "2026-11-05")
        self.assertEqual(record["announcedOn"], "2026-11-01")
        self.assertEqual(record["questions"]["what"]["announcement"], "Move to Entra ID.")
        self.assertEqual(record["questions"]["actions"]["resources"], [{"title": "Entra ID", "url": "https://learn.microsoft.com/azure/"}])
        self.assertEqual(list(record["questions"]), ["what", "actions", "impact", "deadline", "progress"])
        self.assertEqual(len(record["questions"]["progress"]["checklist"]), 4)

    def test_modified_timestamp_null_invalid_and_timezone_rollover(self):
        self.assertIsNone(normalize({**ITEM, "modified": None})["lastUpdatedOn"])
        self.assertEqual(normalize({**ITEM, "modified": "2026-11-05T23:30:00-02:00"})["lastUpdatedOn"], "2026-11-06")
        for modified in ("", "invalid", "2026-11-05", "2026-02-30T00:00:00Z", 42):
            with self.subTest(modified=modified), self.assertRaisesRegex(ValueError, "modified timestamp"):
                normalize({**ITEM, "modified": modified})

    def test_ambiguous_month_only_invalid_and_api_version_dates(self):
        for title in (
            "Retires March 2027", "Retires 31 February 2027", "Retires 2027-99-99",
            "Retires 1 May 2027 and 2 June 2027",
            "Retirement: Azure Container Apps preview API versions 2023-04-01-preview",
            "Azure Digital Twins Control-Plane Preview API Retirement (2020-03-31)",
            "Pod Security Policy is being deprecated with AKS 1.25 and 2023-06-01 API version",
            "We’re ending support for the 2017-03-01-GA API.",
        ):
            with self.subTest(title=title):
                self.assertIsNone(title_date(title))
        for title, expected in (
            ("Retires November 10, 2026", "2026-11-10"), ("Retires 10th November 2026", "2026-11-10"),
            ("Retires 2028-02-29", "2028-02-29"),
            ("Azure Maps API V 2023-06-01 will be retired on September 30th, 2025.", "2025-09-30"),
            ("Use API version 2021-11-01 by 30 September 2026", "2026-09-30"),
            ("API version 2023-04-01-preview retires on 2027-03-31", "2027-03-31"),
        ):
            self.assertEqual(title_date(title), expected)

    def test_html_entities_paragraphs_and_unsafe_links(self):
        result = read_announcement('<p>A &amp; B&nbsp;C</p><p>Next<br>line</p><script>evil()</script><a href="javascript:evil()">bad</a><a href="/updates/">Good</a>')
        self.assertEqual(result["details"], "A & B C\nNext\nline\nbadGood")
        self.assertEqual(result["links"], [{"title": "Good", "url": "https://azure.microsoft.com/updates/"}])
        self.assertEqual(read_announcement("<p>A long\nline with <strong>formatted\ntext</strong>.</p>")["details"], "A long line with formatted text.")

    def test_source_actions_and_month_only_guidance(self):
        description = "<p>Change.</p><h3>Recommended action</h3><p>Migrate to the new API.</p><h3>Help and support</h3><p>Contact us.</p>"
        self.assertEqual(normalize({**ITEM, "description": description})["questions"]["actions"]["recommendedAction"], "Migrate to the new API.")
        unknown = normalize({**ITEM, "title": "Retirement: API keys"})
        self.assertIsNone(unknown["questions"]["deadline"]["date"])
        self.assertIn("March 2027", unknown["questions"]["deadline"]["dateGuidance"])
        self.assertIsNone(unknown["questions"]["actions"]["recommendedAction"])

    def test_nullable_availability_and_malformed_source_links(self):
        record = normalize({**ITEM, "availabilities": None})
        self.assertIsNone(record["questions"]["deadline"]["month"])
        self.assertEqual(record["questions"]["deadline"]["date"], "2027-03-31")
        announcement = read_announcement('<a href="https://[invalid">Invalid</a><a href="https://learn.microsoft.com/">Valid</a>')
        self.assertEqual(announcement["links"], [{"title": "Valid", "url": "https://learn.microsoft.com/"}])

    def test_official_categories_and_product_fallbacks(self):
        self.assertEqual(normalize({**ITEM, "products": []})["services"], ["Azure platform"])
        self.assertEqual(normalize({**ITEM, "productCategories": ["Analytics", " Internet of Things ", "Analytics", "", None]})["categories"], ["Analytics", "Internet of Things"])
        for categories in (None, [], ["", " ", None]):
            self.assertEqual(normalize({**ITEM, "productCategories": categories})["categories"], ["Uncategorized"])
        with self.assertRaises(ValueError):
            normalize({**ITEM, "tags": []})

    def test_complete_pagination_without_next_link(self):
        offsets = []
        def fetcher(url):
            skip = int(parse_qs(urlsplit(url).query)["$skip"][0])
            offsets.append(skip)
            return {"@odata.count": 3, "value": [ITEM, {**ITEM, "id": "two"}] if skip == 0 else [{**ITEM, "id": "three"}]}
        self.assertEqual(len(fetch_retirements(fetcher)), 3)
        self.assertEqual(offsets, [0, 2])

    def test_incomplete_duplicate_malformed_changing_or_oversized_feed_fails(self):
        for payload in (
            {"@odata.count": 1, "value": []}, {"@odata.count": 2, "value": [ITEM, ITEM]},
            {"value": [ITEM]}, {"@odata.count": True, "value": [ITEM]},
            {"@odata.count": 1, "value": [ITEM, {**ITEM, "id": "b"}]},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                fetch_retirements(lambda url: payload)
        pages = iter(({"@odata.count": 2, "value": [ITEM]}, {"@odata.count": 3, "value": [ITEM]}))
        with self.assertRaisesRegex(ValueError, "count changed"):
            fetch_retirements(lambda url: next(pages))
