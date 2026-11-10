"""Verify the generated HTML, public asset paths, and catalog fidelity."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .catalog import QUESTIONS, ROOT, parse_catalog, record_url, retirement_outlook, valid_date


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_site(root=ROOT):
    root = Path(root)
    destination = root / "docs"
    catalog = parse_catalog(json.loads((root / "data" / "retirements.json").read_text(encoding="utf-8")))
    home_html = (destination / "index.html").read_text(encoding="utf-8")
    home = Elements(home_html)
    require(any(tag == "body" and attrs.get("data-home") == "./" for tag, attrs in home.tags), "Homepage links must be relative")
    require(sum(tag == "article" and attrs.get("class") == "card" for tag, attrs in home.tags) == min(24, len(catalog["records"])), "Incorrect initial card count")
    as_of = next((attrs.get("datetime") for tag, attrs in home.tags if tag == "time" and attrs.get("id") == "outlook-date"), None)
    require(isinstance(as_of, str) and valid_date(as_of), "Missing or invalid outlook date")
    cards = re.findall(r'<a class="outlook-card"[^>]*>.*?</a>', home_html, re.S)
    require(len(cards) == 4, "Expected four rolling retirement outlook cards")
    for card, window in zip(cards, retirement_outlook(catalog["records"], as_of)):
        require(f'data-window="{window["key"]}"' in card, "Incorrect retirement outlook window")
        require(f'<strong data-window-count>{window["count"]}</strong>' in card, "Incorrect retirement outlook count")
    paths = set()
    for _, attrs in home.tags:
        href = attrs.get("href") or attrs.get("src")
        if not href or href.startswith(("#", "https:", "http:")):
            continue
        for base in ("https://site.example/", "https://site.example/retirements/"):
            resolved = urljoin(base, href)
            require(resolved.startswith(base), f"Link escapes the site base: {href}")
            path = urlsplit(resolved).path[len(urlsplit(base).path):]
            paths.add(path)
            target = destination / path
            require((target / "index.html" if path.endswith("/") or not path else target).is_file(), f"Missing local target: {href}")
    expected = set()
    for record in catalog["records"]:
        path = record_url(record["id"]).lstrip("/") + "index.html"
        expected.add(path)
        html = (destination / path).read_text(encoding="utf-8")
        heading = re.search(r"<h1>(.*?)</h1>", html, re.S)
        require(heading is not None and "".join(Elements(heading[1]).text) == record["title"], f'{record["id"]}: static title missing')
        article = re.search(r'<article class="detail-content">(.*?)</article>', html, re.S)
        require(article is not None, f'{record["id"]}: static article missing')
        sections = [attrs.get("id") for tag, attrs in Elements(article[1]).tags if tag == "section"]
        require(sections == list(QUESTIONS), f'{record["id"]}: incorrect question order')
        headings = re.findall(r"<h2>(.*?)</h2>", article[1], re.S)
        require(len(headings) == 5, f'{record["id"]}: incorrect question count')
        for key, value in zip(QUESTIONS, headings):
            require("".join(Elements(value).text).endswith(record["questions"][key]["question"]), f'{record["id"]}: {key} heading missing')
        require('data-countdown' in html and 'data-home="../../"' in html, f'{record["id"]}: countdown or home path missing')
        require('src="../../assets/js/main.js"' in html, f'{record["id"]}: script path missing')
    actual = {str(path.relative_to(destination)).replace("\\", "/") for path in (destination / "retirements").glob("*/index.html")}
    require(actual == expected, "Generated retirement pages do not match the catalog")
    require(json.loads((destination / "assets" / "data" / "retirements.json").read_text(encoding="utf-8")) == catalog, "Download differs from the canonical catalog")
    require((destination / ".nojekyll").is_file(), "Missing docs/.nojekyll")
    for private in ("src", "scripts", "tests", "site", "data", "requirements.txt", "package.json"):
        require(not (destination / private).exists(), f"Private source published: {private}")
    for name in ("main.js", "data.js", "catalog.js"):
        require((destination / "assets" / "js" / name).is_file(), f"Missing browser module: {name}")
    for directory in ("css", "js"):
        for source in (root / "site" / "assets" / directory).rglob("*"):
            if source.is_file():
                published = destination / source.relative_to(root / "site")
                require(published.is_file() and published.read_bytes() == source.read_bytes(), f"Published asset is stale: {source}")
    print(f"Verified {len(expected)} static retirement pages, five-question content, catalog download, and {len(paths)} local targets.")


if __name__ == "__main__":
    check_site()
