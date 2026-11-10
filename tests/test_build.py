import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("retirement_builder", ROOT / "site" / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class StaticSiteTests(unittest.TestCase):
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
