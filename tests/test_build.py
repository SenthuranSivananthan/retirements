import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from scripts.catalog import DETAIL_QUESTIONS, format_date, prepare_site, record_url, record_urls, retirement_outlook
from scripts.check_site import check_site
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
        for question in record["questions"].values():
            question.pop("html", None)
        record["questions"]["progress"].pop("tracking", None)
        record.pop("sourceReview", None)
        record["id"] = "example"
        record["questions"]["deadline"].update({"date": None, "month": None})
        record["title"] = 'Retirement <script>alert("unsafe")</script>'
        record["questions"]["what"]["announcement"] = "First <script>unsafe</script>\nSecond line"
        self.view = {
            "record": record, "status": "unknown", "label": "Date to confirm",
            "countdown": "Retirement date to confirm", "year": "unknown", "categories": ["Uncategorized"],
            "url": record_url(record), "deadline": "Date not specified", "announced": "Date not specified",
            "customerLeadTime": "Not calculable", "updated": "Not provided by source", "sourceUrl": None, "resources": [],
            "support": {"url": None, "title": "Support"}, "advisor": {"url": None, "title": "Advisor"},
            "sections": [{"id": key, "question": record["questions"][key]["question"]} for key in DETAIL_QUESTIONS],
        }
        self.metadata = {
            "byId": {"example": self.view}, "buildDate": "2026-11-10", "count": 1,
            "navigation": [], "categories": [], "services": [], "initialIds": ["example"], "upcoming": 0, "soon": 0,
            "refreshed": "10 Nov 2026",
            "outlook": retirement_outlook([record], "2026-11-10"),
        }
        self.save()

    def save(self):
        directory = self.root / "site" / "_data"
        directory.mkdir(exist_ok=True)
        (directory / "site.json").write_text(json.dumps(self.metadata), encoding="utf-8")

    def detail_path(self):
        return self.root / "docs" / self.view["url"].lstrip("/") / "index.html"

    def test_complete_static_content_relative_links_and_escaping(self):
        self.assertEqual(builder.build_site(self.root), 1)
        destination = self.root / "docs"
        html = self.detail_path().read_text(encoding="utf-8")
        self.assertIn('data-home="../../../"', html)
        self.assertIn('src="../../../assets/js/main.js"', html)
        positions = [html.index(f'<section id="{key}">') for key in DETAIL_QUESTIONS]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("<script>unsafe</script>", html)
        self.assertIn("First &lt;script&gt;unsafe&lt;/script&gt;<br>Second line", html)
        self.assertIn("Retirement date to confirm", html)
        self.assertIn("<dt>Customer lead time</dt><dd>Not calculable</dd>", html)
        self.assertIn('<span class="badge amber customer-lead-time-pill">Lead time: Not calculable</span>', html)
        self.assertTrue(all(line == line.rstrip() for line in html.splitlines()))
        self.assertTrue((destination / ".nojekyll").is_file())
        self.assertFalse((destination / "src").exists())
        self.assertFalse((destination / "templates").exists())
        home = (destination / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Azure Retirement Catalog</title>", home)
        for window in ("retired-year", "6", "12", "18"):
            self.assertIn(f'data-window="{window}"', home)
            self.assertIn(f'?window={window}&amp;sort=date#catalog', home)
        self.assertIn('<label><span>Retirement window</span><select id="window">', home)
        self.assertNotIn('<span>Date window</span>', home)
        document = parse(home, namespaceHTMLElements=False)
        timeline_date = document.find(".//div[@class='timeline-date']")
        self.assertEqual([label.text for label in timeline_date.findall("span")
                          if "timeline-date-label" in label.attrib.get("class", "").split()],
                         ["Retirement date", "Customer lead time"])
        self.assertEqual(timeline_date.find("span[@class='timeline-lead-time']").text, "Not calculable")
        announced_options = document.findall(".//select[@id='announced-year']/option")
        self.assertEqual([option.attrib["value"] for option in announced_options], ["", "2026", "2025", "2024", "2023"])
        self.assertEqual(announced_options[1].text, "Announced in 2026")
        self.assertEqual(document.find(".//h1[@id='hero-title']").text, "Azure Retirement Catalog")
        self.assertIsNone(document.find(".//select[@id='announced']"))
        self.assertEqual(document.find(".//span[@id='year-navigation-count']").text, "1")
        self.assertIn("hidden", document.find(".//p[@id='navigation-empty']").attrib)
        self.assertEqual(document.find(".//div[@id='results']").attrib["class"], "retirement-timeline")
        reset = document.find(".//button[@id='reset-filters']")
        self.assertEqual(reset.attrib["type"], "button")
        self.assertEqual(reset.text, "Reset filters")
        self.assertIsNone(document.find(".//select[@id='sort']"))
        hero_links = document.findall(".//div[@class='hero-cta']/a")
        self.assertEqual(len(hero_links), 1)
        self.assertEqual(hero_links[0].attrib["href"], "#catalog")
        self.assertNotIn("Review the next 90 days", home)
        layout = document.find(".//div[@class='layout']")
        self.assertEqual(layout[0].attrib.get("id"), "navigation")
        page_content = layout.find("div[@class='page-content']")
        self.assertIsNotNone(page_content.find("section[@id='home-hero']"))
        self.assertIsNotNone(page_content.find("main[@id='main']"))
        detail_document = parse(html, namespaceHTMLElements=False)
        empty_navigation = detail_document.find(".//p[@id='navigation-empty']")
        self.assertIn("hidden", empty_navigation.attrib)
        self.assertEqual(empty_navigation.find("a").attrib["href"], "../../../#catalog")
        detail_shortcut = detail_document.find(".//aside//a[@data-nav='soon']")
        self.assertEqual(detail_shortcut.attrib["href"], "../../../?status=soon&sort=date#catalog")
        self.assertIsNotNone(detail_document.find(".//div[@class='page-content']/main[@id='main']"))
        hero_outlook = document.find(".//section[@id='home-hero']/div[@class='hero-in']/section[@class='outlook']")
        self.assertIsNotNone(hero_outlook)
        self.assertEqual(len(hero_outlook.findall(".//a[@data-window]")), 4)
        self.assertEqual(len(document.findall(".//section[@class='outlook']")), 1)
        self.assertIsNone(document.find(".//main//section[@class='outlook']"))
        self.assertIn("hidden", document.find(".//section[@class='stats']").attrib)

    def test_question_html_renders_semantic_markup_and_escapes_text(self):
        markup = (
            "<p>First line</p><p>Second line<br>with <strong>emphasis</strong> and &lt;script&gt; text.</p>"
            "<ul><li>Item</li></ul><ol><li>Step</li></ol>"
        )
        for section in DETAIL_QUESTIONS:
            self.view["record"]["questions"][section]["html"] = markup
        self.save()
        builder.build_site(self.root)
        html = self.detail_path().read_text(encoding="utf-8")
        document = parse(html, namespaceHTMLElements=False)
        for section in DETAIL_QUESTIONS:
            with self.subTest(section=section):
                content = document.find(f".//section[@id='{section}']/div[@class='rich-content']")
                self.assertIsNotNone(content)
                paragraphs = content.findall("./p")
                self.assertEqual(paragraphs[0].text, "First line")
                self.assertIsNotNone(paragraphs[1].find("./br"))
                self.assertEqual(paragraphs[1].find("./strong").text, "emphasis")
                self.assertEqual(content.find("./ul/li").text, "Item")
                self.assertEqual(content.find("./ol/li").text, "Step")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script> text.", html)

    def test_learn_guidance_button_follows_all_actions_content(self):
        actions = self.view["record"]["questions"]["actions"]
        actions["supportGuidance"] = "Contact your support team."
        self.view["support"] = {"url": "https://azure.microsoft.com/support/", "title": "Support options"}
        guidance = "https://learn.microsoft.com/azure/example/migrate"
        for rich in (False, True):
            for source in (None, guidance):
                with self.subTest(rich=rich, source=source):
                    if rich:
                        actions["html"] = "<p>Migration steps and cautions.</p>"
                    else:
                        actions.pop("html", None)
                    self.view["guidanceSource"] = source
                    self.save()
                    builder.build_site(self.root)
                    document = parse(self.detail_path().read_text(encoding="utf-8"), namespaceHTMLElements=False)
                    section = document.find(".//section[@id='actions']")
                    support = section.find("p/a[@href='https://azure.microsoft.com/support/']")
                    self.assertIsNotNone(support)
                    self.assertIn("Contact your support team.", "".join(section.itertext()))
                    button = section.find(f"a[@href='{guidance}']")
                    if source:
                        self.assertEqual(section[-1], button)
                        self.assertIn("Open Microsoft Learn guidance", "".join(button.itertext()))
                        self.assertEqual(section[-2].find("a"), support)
                    else:
                        self.assertIsNone(button)
                        self.assertEqual(section[-1].find("a"), support)

    def test_json_enrichment_displays_manual_source_and_progress_without_extra_fallback(self):
        record = self.view["record"]
        record["sourceLabel"] = "User-provided retirement"
        record["enrichment"] = {"automaticRevision": "current"}
        record["questions"]["progress"]["html"] = "<p>Use the documented inventory query; record results locally.</p>"
        self.save()
        builder.build_site(self.root)
        document = parse(self.detail_path().read_text(encoding="utf-8"), namespaceHTMLElements=False)
        facts = document.find(".//div[@class='fact-card']/dl")
        self.assertIn("User-provided retirement", "".join(facts.itertext()))
        progress = "".join(document.find(".//section[@id='progress']").itertext())
        self.assertIn("Use the documented inventory query", progress)
        self.assertNotIn("Tracking guidance is not available", progress)
        data = self.root / "data"
        data.mkdir()
        (data / "retirements.json").write_text(json.dumps({
            "schemaVersion": 2, "source": "https://example.com/retirements",
            "retrievedAt": "2026-11-10T00:00:00Z", "enrichmentPipeline": "json-v1", "records": [record],
        }), encoding="utf-8")
        shutil.copytree(ROOT / "site" / "assets" / "js", self.root / "site" / "assets" / "js", dirs_exist_ok=True)
        prepare_site(self.root)
        builder.build_site(self.root)
        check_site(self.root)

    def test_rich_enrichment_html_renders_headings_lists_and_code(self):
        markup = (
            "<h3>Migration steps</h3><p>Review the <strong>affected</strong> SKU.</p>"
            "<ul><li>Inventory <code>sku</code>.</li></ul>"
            "<ol><li>Assign an owner.</li><li>Validate the replacement.</li></ol>"
            "<pre><code>az resource list</code></pre><p>Keep <em>exceptions</em> visible.<br>Track results.</p>"
        )
        for section in DETAIL_QUESTIONS:
            self.view["record"]["questions"][section]["html"] = markup
        self.view["record"]["enrichment"] = {"automaticRevision": "current"}
        self.save()
        builder.build_site(self.root)
        document = parse(self.detail_path().read_text(encoding="utf-8"), namespaceHTMLElements=False)
        content = document.find(".//section[@id='actions']/div[@class='rich-content']")
        self.assertIsNotNone(content.find("./h3"))
        self.assertIsNotNone(content.find("./ul/li/code"))
        self.assertEqual(len(content.findall("./ol/li")), 2)
        self.assertEqual(content.find("./p/strong").text, "affected")
        self.assertEqual(content.find("./p/em").text, "exceptions")
        self.assertEqual(content.find("./pre/code").text, "az resource list")
        self.assertIsNotNone(content.find("./p/br"))

    def test_static_timeline_groups_categories_services_and_orders_deadlines_descending(self):
        self.metadata["byId"] = {}
        self.metadata["initialIds"] = []
        for identifier, title, deadline, categories, services in (
            ("a", "Zulu", "2028-01-01", ["Compute"], ["VM"]),
            ("b", "Earlier", "2026-01-01", ["Compute"], ["VM"]),
            ("c", "Unknown", None, ["Compute"], ["VM"]),
            ("d", "Alpha", "2028-01-01", ["Compute"], ["VM"]),
            ("e", "Shared", "2027-01-01", ["Compute", "Storage"], ["VM", "Blob"]),
        ):
            view = copy.deepcopy(self.view)
            view["record"].update({"id": identifier, "title": title, "categories": categories, "services": services})
            view["record"]["questions"]["deadline"].update({"date": deadline, "month": "May 2029"})
            view.update({"url": record_url(view["record"]), "deadline": format_date(deadline)})
            self.metadata["byId"][identifier] = view
            self.metadata["initialIds"].append(identifier)
        self.metadata["count"] = 5
        self.save()
        builder.build_site(self.root)
        document = parse((self.root / "docs" / "index.html").read_text(encoding="utf-8"), namespaceHTMLElements=False)
        categories = document.findall(".//div[@id='results']/section")
        self.assertEqual([group.attrib["data-category"] for group in categories], ["Compute", "Storage"])
        services = categories[0].findall("section")
        self.assertEqual([group.attrib["data-service"] for group in services], ["Blob", "VM"])
        entries = services[1].findall("ol/li")
        self.assertEqual([entry.attrib["data-record"] for entry in entries], ["d", "a", "e", "b", "c"])
        self.assertEqual(entries[0].find(".//time").attrib["datetime"], "2028-01-01")
        self.assertEqual(entries[0].find(".//span[@class='timeline-date-label']").text, "Retirement date")
        self.assertIsNone(entries[0].find(".//span[@class='timeline-announced']"))
        self.assertIsNone(entries[-1].find(".//div[@class='timeline-date']/time"))
        self.assertIn("Date to confirm", "".join(entries[-1].itertext()))
        ids = [node.attrib["id"] for node in document.iter() if "id" in node.attrib]
        self.assertEqual(len(ids), len(set(ids)))

    def test_source_review_renders_sources_once_after_questions_without_original_box(self):
        record = self.view["record"]
        record["sourceReview"] = {
            "reviewedOn": "2026-11-11", "status": "needs-review",
            "issues": ["Conflicting source years <script>unsafe</script>"],
            "originalAnnouncement": "Original <script>unsafe</script>\r\nSecond line\n\n  \nLast paragraph",
            "sources": [{
                "title": "Learn <script>unsafe</script>",
                "url": "https://learn.microsoft.com/en-us/azure/example",
                "sections": ["what", "actions", "impact", "deadline", "progress"],
                "note": "Scope <img src=x onerror=unsafe>",
            }],
        }
        self.save()
        builder.build_site(self.root)
        html = self.detail_path().read_text(encoding="utf-8")
        document = parse(html, namespaceHTMLElements=False)
        article = document.find(".//article[@class='detail-content']")
        self.assertEqual([section.attrib["id"] for section in article.findall("section")],
                         list(DETAIL_QUESTIONS))
        self.assertEqual([section.find("h2/span").text for section in article.findall("section")],
                         ["1", "2", "3", "4", "5"])
        nav = document.find(".//nav[@class='article-nav']")
        self.assertEqual([link.attrib["href"] for link in nav.findall("a")[:5]],
                         ["#" + key for key in DETAIL_QUESTIONS])
        reading = article.find("div[@id='further-reading']")
        self.assertEqual(article[-1], reading)
        self.assertIsNone(document.find(".//div[@class='fact-card']/div[@id='further-reading']"))
        self.assertEqual(reading.find("h3").text, "References")
        links = reading.findall(".//a[@href='https://learn.microsoft.com/en-us/azure/example']")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].attrib["rel"], "noopener noreferrer")
        self.assertIsNone(reading.find(".//details"))
        nav_link = document.find(".//nav[@class='article-nav']/a[@href='#further-reading']")
        self.assertEqual(nav_link.text, "References")
        self.assertNotIn("About this source", html)
        self.assertNotIn("Sources for this answer", html)
        self.assertNotIn("Resources from the announcement", html)
        self.assertIn("Source review needs verification", html)
        self.assertIn('datetime="2026-11-11"', html)
        self.assertNotIn("<script>unsafe</script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("Microsoft Update", html)
        self.assertNotIn("Original &lt;script&gt;", html)
        self.assertNotIn("Original announcement from the feed", html)
        self.assertEqual(record["sourceReview"]["originalAnnouncement"],
                         "Original <script>unsafe</script>\r\nSecond line\n\n  \nLast paragraph")

        record["sourceReview"]["status"] = "enriched"
        self.save()
        builder.build_site(self.root)
        html = self.detail_path().read_text(encoding="utf-8")
        self.assertNotIn("Source-enriched content", html)
        self.assertNotIn("Source review needs verification", html)
        self.assertNotIn("Microsoft Update", html)

    def test_further_reading_resolves_and_deduplicates_resources_without_mutating_evidence(self):
        record = self.view["record"]
        record["questions"]["actions"]["resources"] = [
            {"title": "Migration instructions", "url": "https://go.microsoft.com/fwlink/?linkid=1"},
            {"title": "Repeated guide", "url": "https://learn.microsoft.com/en-us/azure/migrate"},
            {"title": "Versioned guide", "url": "https://learn.microsoft.com/en-us/azure/migrate?view=v2#steps"},
            {"title": "Section link", "url": "https://learn.microsoft.com/en-us/azure/migrate#limits"},
            {"title": "Unsafe link", "url": "javascript:alert(1)"},
        ]
        record["sourceReview"] = {
            "sources": [{
                "title": "Migration guide", "url": "https://learn.microsoft.com/en-us/azure/migrate",
                "sections": ["actions"], "note": "Scope of the migration.",
            }],
            "resourceChecks": [{
                "url": "https://go.microsoft.com/fwlink/?linkid=1",
                "resolvedUrl": "https://learn.microsoft.com/en-us/azure/migrate",
            }],
        }
        before = copy.deepcopy(record)
        reading = builder.further_reading(record)
        self.assertEqual([link["url"] for link in reading], [
            "https://learn.microsoft.com/en-us/azure/migrate",
            "https://learn.microsoft.com/en-us/azure/migrate?view=v2#steps",
            "https://learn.microsoft.com/en-us/azure/migrate#limits",
        ])
        self.assertEqual(reading[0]["title"], "Migration guide")
        self.assertEqual(reading[0]["note"], "Scope of the migration.")
        self.assertEqual(record, before)

    def test_excluded_references_are_not_displayed_even_via_redirect(self):
        record = self.view["record"]
        record["questions"]["actions"]["resources"] = [
            {"title": "Short link", "url": "https://go.microsoft.com/fwlink/?linkid=1"},
            {"title": "Good guide", "url": "https://learn.microsoft.com/en-us/azure/good"},
        ]
        record["sourceReview"] = {
            "sources": [{"title": "Gone", "url": "https://learn.microsoft.com/en-us/azure/gone"}],
            "resourceChecks": [{"url": "https://go.microsoft.com/fwlink/?linkid=1",
                                "resolvedUrl": "https://learn.microsoft.com/en-us/azure/gone"}],
            "excludedReferences": [{"url": "https://learn.microsoft.com/en-us/azure/gone",
                                    "checkedOn": "2026-11-11", "httpStatus": 404}],
        }
        before = copy.deepcopy(record)
        self.assertEqual([reference["url"] for reference in builder.further_reading(record)],
                         ["https://learn.microsoft.com/en-us/azure/good"])
        self.assertEqual(record, before)

    def test_unreviewed_resources_render_in_further_reading_and_empty_lists_are_omitted(self):
        record = self.view["record"]
        record["questions"]["actions"]["resources"] = [{
            "title": "Guide <script>unsafe</script>", "url": "https://learn.microsoft.com/en-us/azure/guide",
        }]
        self.save()
        builder.build_site(self.root)
        path = self.detail_path()
        document = parse(path.read_text(encoding="utf-8"), namespaceHTMLElements=False)
        link = document.find(".//article[@class='detail-content']/div[@id='further-reading']//a")
        self.assertEqual(link.attrib["href"], "https://learn.microsoft.com/en-us/azure/guide")
        self.assertTrue(link.text.startswith("Guide <script>unsafe</script>"))
        self.assertIsNone(document.find(".//section[@id='actions']//a"))
        record["questions"]["actions"]["resources"] = []
        self.save()
        builder.build_site(self.root)
        document = parse(path.read_text(encoding="utf-8"), namespaceHTMLElements=False)
        self.assertIsNone(document.find(".//*[@id='further-reading']"))
        self.assertIsNone(document.find(".//nav[@class='article-nav']/a[@href='#further-reading']"))

    def test_progress_shows_only_documented_tracking_or_unavailable_message(self):
        record = self.view["record"]
        self.save()
        builder.build_site(self.root)
        path = self.detail_path()
        document = parse(path.read_text(encoding="utf-8"), namespaceHTMLElements=False)
        progress = document.find(".//section[@id='progress']")
        self.assertIn("Tracking guidance is not available for this retirement.", "".join(progress.itertext()))
        self.assertIsNone(progress.find(".//input"))
        record["questions"]["progress"]["tracking"] = {
            "guidance": "Inspect the documented resources.",
            "sourceUrl": "https://learn.microsoft.com/en-us/azure/example",
        }
        self.save()
        builder.build_site(self.root)
        document = parse(path.read_text(encoding="utf-8"), namespaceHTMLElements=False)
        progress = document.find(".//section[@id='progress']")
        self.assertIn("Inspect the documented resources.", "".join(progress.itertext()))
        self.assertNotIn("Tracking guidance is not available", "".join(progress.itertext()))
        self.assertEqual(progress.find(".//a").attrib["href"], record["questions"]["progress"]["tracking"]["sourceUrl"])
        self.assertIsNone(progress.find(".//input"))

    def test_category_dropdown_lists_all_prepared_categories_with_an_all_option(self):
        self.metadata["categories"] = ["Compute", "Storage", "Uncategorized"]
        self.save()
        builder.build_site(self.root)
        document = parse((self.root / "docs" / "index.html").read_text(encoding="utf-8"), namespaceHTMLElements=False)
        options = document.findall(".//select[@id='category']/option")
        self.assertEqual([option.attrib["value"] for option in options], ["", "Compute", "Storage", "Uncategorized"])
        self.assertEqual(options[0].text, "All categories")

    def test_all_retirement_details_are_recreated_and_unrelated_files_are_preserved(self):
        builder.build_site(self.root)
        destination = self.root / "docs"
        detail = self.detail_path()
        detail.write_text("stale detail page", encoding="utf-8")
        notes = detail.parent / "notes.txt"
        notes.write_text("Preserve this file.", encoding="utf-8")
        orphan = destination / "retirements" / "2030-01-01" / "orphan" / "index.html"
        orphan.parent.mkdir(parents=True)
        orphan.write_text("orphaned detail", encoding="utf-8")
        download = destination / "downloads" / "custom.txt"
        download.parent.mkdir()
        download.write_text("Preserve this download.", encoding="utf-8")
        builder.build_site(self.root)
        rendered = detail.read_text(encoding="utf-8")
        document = parse(rendered, namespaceHTMLElements=False)
        self.assertEqual(document.find(".//h1").text, self.view["record"]["title"])
        self.assertNotIn("stale detail page", rendered)
        self.assertFalse(notes.exists())
        self.assertFalse(orphan.parent.exists())
        self.assertTrue(download.is_file())

    def test_deadline_changes_move_pages_and_remove_stale_and_legacy_paths(self):
        builder.build_site(self.root)
        retirement_root = self.root / "docs" / "retirements"
        legacy = retirement_root / "example"
        legacy.mkdir()
        (legacy / "index.html").write_text("Old flat page", encoding="utf-8")
        (legacy / "notes.txt").write_text("Preserve this file.", encoding="utf-8")
        for deadline, previous in (
            ("2026-05-12", "unknown-date"),
            ("2027-01-02", "2026-05-12"),
            (None, "2027-01-02"),
        ):
            self.view["record"]["questions"]["deadline"]["date"] = deadline
            self.view["url"] = record_url(self.view["record"])
            self.save()
            self.assertEqual(builder.build_site(self.root), 1)
            self.assertFalse((retirement_root / previous).exists())
            target = self.detail_path()
            self.assertTrue(target.is_file())
            document = parse(target.read_text(encoding="utf-8"), namespaceHTMLElements=False)
            self.assertEqual(document.find(".//body").attrib["data-home"], "../../../")
            home = (self.root / "docs" / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'href=".{self.view["url"]}"', home)
        self.assertFalse((legacy / "index.html").exists())
        self.assertFalse(legacy.exists())
        self.assertEqual(len(list(retirement_root.rglob("index.html"))), 1)

    def test_title_changes_move_pages_and_remove_the_old_slug(self):
        builder.build_site(self.root)
        old = self.detail_path()
        self.view["record"]["title"] = "Updated: retirement title"
        self.view["url"] = record_url(self.view["record"])
        self.save()
        builder.build_site(self.root)
        self.assertFalse(old.exists())
        self.assertTrue(self.detail_path().is_file())
        self.assertIn("/updated-retirement-title/", self.view["url"])

    def test_duplicate_title_slugs_generate_distinct_pages(self):
        self.view["record"]["title"] = "Same retirement"
        other = copy.deepcopy(self.view)
        other["record"]["id"] = "second"
        self.metadata["byId"]["second"] = other
        self.metadata["initialIds"].append("second")
        self.metadata["count"] = 2
        urls = record_urls([self.view["record"], other["record"]])
        for identifier, view in self.metadata["byId"].items():
            view["url"] = urls[identifier]
        self.save()
        self.assertEqual(builder.build_site(self.root), 2)
        home = (self.root / "docs" / "index.html").read_text(encoding="utf-8")
        for identifier, url in urls.items():
            self.assertTrue((self.root / "docs" / url.lstrip("/") / "index.html").is_file())
            self.assertIn(f'href=".{url}"', home)
            self.assertIn(f"same-retirement--{identifier}", url)

    def test_invalid_deadline_folder_cannot_escape_the_output_directory(self):
        for deadline in ("../../outside", "2026-02-30", ""):
            self.view["record"]["questions"]["deadline"]["date"] = deadline
            self.save()
            with self.subTest(deadline=deadline), self.assertRaisesRegex(ValueError, "Invalid retirement date"):
                builder.build_site(self.root)
            self.assertFalse((self.root / "docs").exists())

    def test_retirement_window_lists_all_known_years_after_rolling_windows_without_status_dropdown(self):
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

    @unittest.skipUnless(shutil.which("node"), "Node.js is optional")
    def test_detail_sidebar_ignores_directory_filters_but_directory_sidebar_retains_them(self):
        program = r"""
            import assert from 'node:assert/strict';
            import { readFile } from 'node:fs/promises';
            const catalogSource = await readFile('site/assets/js/catalog.js', 'utf8');
            const { filterRecords, groupRetirements, retirementYear, categoriesOf } = await import(
                `data:text/javascript;base64,${Buffer.from(catalogSource).toString('base64')}`
            );
            const source = await readFile('site/assets/js/main.js', 'utf8');
            const updateNav = source.slice(source.indexOf('function updateNav()'),
                source.indexOf('function renderTimelineEntry('));
            const visibleRecords = [
                { id: 'current', title: 'Matching retirement', year: '2030', category: 'Compute' },
                { id: 'neighbor', title: 'Another retirement', year: '2030', category: 'Compute' },
                { id: 'other-year', title: 'Different retirement', year: '2031', category: 'Storage' },
            ].map(record => ({
                ...record, categories: [record.category], services: ['Example'], service: 'Example',
                summary: '', announcedOn: '2026-01-01',
                questions: { what: { announcement: '' }, deadline: { date: `${record.year}-01-01`, month: null } },
            }));
            const filters = { q: 'Matching', year: '2030', category: 'Compute', status: 'all' };
            const directoryLink = context => '/?' + new URLSearchParams(context);
            const detailLink = (record, context) => `/retirements/${record.id}/?` + new URLSearchParams(context);
            const node = (dataset = {}, parent = null) => ({
                dataset, hidden: false, attributes: {}, parentElement: parent,
                closest() { return dataset.yearGroup || dataset.categoryGroup ? this : parent; },
                setAttribute(key, value) { this.attributes[key] = value; },
                removeAttribute(key) { delete this.attributes[key]; },
            });
            for (const isDirectory of [true, false]) {
                const activeRecord = isDirectory ? null : visibleRecords[0];
                const links = [];
                const yearGroups = groupRetirements(visibleRecords).map(year => {
                    const group = node({ yearGroup: year.year });
                    const count = node(), all = node({ year: year.year, category: '' });
                    links.push(all);
                    const categories = year.categories.map(category => {
                        const branch = node({ categoryGroup: category.name }, group);
                        const count = node(), all = node({ year: year.year, category: category.name }, branch);
                        links.push(all);
                        const records = category.records.map(record => node({
                            record: record.id, year: year.year, category: category.name,
                        }, branch));
                        links.push(...records);
                        branch.querySelector = selector => selector === '.category-all' ? all : count;
                        branch.querySelectorAll = () => records;
                        return branch;
                    });
                    group.querySelector = selector => selector.includes('summary') ? count : all;
                    group.querySelectorAll = () => categories;
                    return group;
                });
                const total = node(), empty = node();
                const element = selector => selector === '#year-navigation-count' ? total : empty;
                const document = { querySelectorAll: selector => selector.includes('.year-group') ? yearGroups : links };
                eval(updateNav + '\nupdateNav();');
                assert.equal(total.textContent, isDirectory ? '1' : '3');
                assert.equal(empty.hidden, true);
                assert.deepEqual(links.filter(link => link.dataset.record && !link.hidden)
                    .map(link => link.dataset.record).sort(),
                    isDirectory ? ['current'] : ['current', 'neighbor', 'other-year']);
                assert.equal(yearGroups.find(group => group.dataset.yearGroup === '2031').hidden, isDirectory);
                if (!isDirectory) {
                    const current = links.find(link => link.dataset.record === 'current');
                    assert.equal(current.attributes['aria-current'], 'page');
                    assert.equal(current.parentElement.open, true);
                    assert.equal(current.parentElement.parentElement.open, true);
                    for (const link of links) {
                        assert.equal(new URL(link.href, 'https://example.test').searchParams.has('q'), false);
                    }
                    for (const group of yearGroups) {
                        const count = group.querySelector(':scope > summary .nav-count');
                        assert.equal(count.textContent, group.dataset.yearGroup === '2030' ? '2' : '1');
                    }
                }
            }
        """
        result = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", program],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
