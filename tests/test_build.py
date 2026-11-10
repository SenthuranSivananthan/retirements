import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from scripts.catalog import retirement_outlook
from html5lib import parse

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("retirement_builder", ROOT / "site" / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class StaticSiteTests(unittest.TestCase):
    def test_asset_copy_replaces_existing_content_and_cleans_failed_temporary_files(self):
        source = self.root / "source.js"
        target = self.root / "published.js"
        source.write_text("export const value = 'updated';", encoding="utf-8")
        target.write_text("old", encoding="utf-8")
        builder.copy_asset(source, target)
        self.assertEqual(target.read_bytes(), source.read_bytes())
        with patch.object(Path, "replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                builder.copy_asset(source, target)
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(list(self.root.glob(".build-*.tmp")), [])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = self.root / "site"
        shutil.copytree(ROOT / "site" / "templates", source / "templates")
        shutil.copyfile(ROOT / "site" / "config.json", source / "config.json")
        for directory in ("css", "js", "data"):
            (source / "assets" / directory).mkdir(parents=True)
        (source / "assets" / "css" / "style.css").write_text("body {}", encoding="utf-8")
        record = copy.deepcopy(json.loads((ROOT / "data" / "retirements.json").read_text(encoding="utf-8"))["records"][0])
        record["id"] = "example"
        record["title"] = 'Retirement <script>alert("unsafe")</script>'
        record["questions"]["what"]["announcement"] = "First <script>unsafe</script>\nSecond line"
        self.view = {
            "record": record, "status": "unknown", "label": "Date to confirm",
            "countdown": "Retirement date to confirm", "year": "unknown", "categories": ["Uncategorized"],
            "url": "/retirements/example/", "deadline": "Date not specified", "announced": "Date not specified",
            "updated": "Not provided by source", "sourceUrl": None, "resources": [],
            "support": {"url": None, "title": "Support"}, "advisor": {"url": None, "title": "Advisor"},
            "sections": [{"id": key, "question": value["question"]} for key, value in record["questions"].items()],
        }
        self.metadata = {
            "byId": {"example": self.view}, "buildDate": "2026-11-10", "count": 1,
            "navigation": [], "services": [], "initialIds": ["example"], "upcoming": 0, "soon": 0,
            "refreshed": "10 Nov 2026",
            "outlook": retirement_outlook([record], "2026-11-10"),
        }
        self.save()

    def save(self):
        directory = self.root / "site" / "_data"
        directory.mkdir(exist_ok=True)
        (directory / "site.json").write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_complete_static_content_relative_links_and_escaping(self):
        self.assertEqual(builder.build_site(self.root), 1)
        destination = self.root / "docs"
        html = (destination / "retirements" / "example" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-home="../../"', html)
        self.assertIn('src="../../assets/js/main.js"', html)
        positions = [html.index(f'<section id="{key}">') for key in ("what", "actions", "impact", "deadline", "progress")]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("<script>unsafe</script>", html)
        self.assertIn("First &lt;script&gt;unsafe&lt;/script&gt;<br>Second line", html)
        self.assertIn("Retirement date to confirm", html)
        self.assertTrue(all(line == line.rstrip() for line in html.splitlines()))
        self.assertTrue((destination / ".nojekyll").is_file())
        self.assertFalse((destination / "src").exists())
        self.assertFalse((destination / "templates").exists())
        home = (destination / "index.html").read_text(encoding="utf-8")
        for window in ("retired-year", "6", "12", "18"):
            self.assertIn(f'data-window="{window}"', home)
            self.assertIn(f'?window={window}&amp;sort=date#catalog', home)
        self.assertIn('id="window"', home)
        document = parse(home, namespaceHTMLElements=False)
        shortcut = document.find(".//div[@class='hero-cta']/a[@class='button ghost']")
        self.assertEqual(shortcut.attrib["href"], "./?status=soon&sort=date#catalog")
        layout = document.find(".//div[@class='layout']")
        self.assertEqual(layout[0].attrib.get("id"), "navigation")
        page_content = layout.find("div[@class='page-content']")
        self.assertIsNotNone(page_content.find("section[@id='home-hero']"))
        self.assertIsNotNone(page_content.find("main[@id='main']"))
        detail_document = parse(html, namespaceHTMLElements=False)
        detail_shortcut = detail_document.find(".//aside//a[@data-nav='soon']")
        self.assertEqual(detail_shortcut.attrib["href"], "../../?status=soon&sort=date#catalog")
        self.assertIsNotNone(detail_document.find(".//div[@class='page-content']/main[@id='main']"))
        hero_outlook = document.find(".//section[@id='home-hero']/div[@class='hero-in']/section[@class='outlook']")
        self.assertIsNotNone(hero_outlook)
        self.assertEqual(len(hero_outlook.findall(".//a[@data-window]")), 4)
        self.assertEqual(len(document.findall(".//section[@class='outlook']")), 1)
        self.assertIsNone(document.find(".//main//section[@class='outlook']"))
        self.assertIn("hidden", document.find(".//section[@class='stats']").attrib)

    def test_stale_pages_are_removed_but_unrelated_files_are_preserved(self):
        builder.build_site(self.root)
        destination = self.root / "docs"
        notes = destination / "retirements" / "example" / "notes.txt"
        notes.write_text("Preserve this file.", encoding="utf-8")
        download = destination / "downloads" / "custom.txt"
        download.parent.mkdir()
        download.write_text("Preserve this download.", encoding="utf-8")
        self.metadata["byId"] = {}
        self.metadata["initialIds"] = []
        self.metadata["count"] = 0
        self.save()
        builder.build_site(self.root)
        self.assertFalse((notes.parent / "index.html").exists())
        self.assertEqual(notes.read_text(encoding="utf-8"), "Preserve this file.")
        self.assertTrue(download.is_file())

    def test_date_window_lists_all_known_years_after_rolling_windows_without_status_dropdown(self):
        self.metadata["navigation"] = [
            {"year": year, "label": year, "count": 1, "categories": []}
            for year in ("2029", "2028", "2020", "unknown")
        ]
        self.save()
        builder.build_site(self.root)
        document = parse((self.root / "docs" / "index.html").read_text(encoding="utf-8"), namespaceHTMLElements=False)
        self.assertIsNone(document.find(".//select[@id='status']"))
        options = document.findall(".//select[@id='window']/option")
        self.assertEqual(
            [option.attrib["value"] for option in options],
            ["", "retired-year", "6", "12", "18", "2029", "2028", "2020"],
        )
        self.assertEqual([option.text for option in options[-3:]], ["2029", "2028", "2020"])

    def test_dot_segments_cannot_overwrite_the_homepage(self):
        self.view["record"]["id"] = ".."
        self.metadata["byId"] = {"..": self.view}
        self.save()
        with self.assertRaisesRegex(ValueError, "Invalid retirement ID"):
            builder.build_site(self.root)
        self.assertFalse((self.root / "docs").exists())

    def test_missing_template_data_fails_instead_of_publishing_blank_content(self):
        del self.metadata["count"]
        self.save()
        from jinja2 import UndefinedError
        with self.assertRaises(UndefinedError):
            builder.build_site(self.root)


if __name__ == "__main__":
    unittest.main()
