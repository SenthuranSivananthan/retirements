"""Generate the GitHub Pages website in docs using prepared catalog metadata."""

import json
import argparse
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context
from markupsafe import Markup, escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.catalog import prepare_site
from scripts.check_site import check_site


@pass_context
def relative_url(context, value):
    return context["home"] + value.lstrip("/")


def build_site(root=ROOT):
    root = Path(root)
    source = root / "site"
    destination = root / "docs"
    config = json.loads((source / "config.json").read_text(encoding="utf-8"))
    metadata = json.loads((source / "_data" / "site.json").read_text(encoding="utf-8"))
    for identifier, view in metadata["byId"].items():
        if not identifier or identifier in {".", ".."} or view["record"]["id"] != identifier:
            raise ValueError(f"Invalid retirement ID in prepared metadata: {identifier!r}")
    environment = Environment(
        loader=FileSystemLoader(source / "templates"),
        autoescape=True,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["relative_url"] = relative_url
    environment.filters["url_encode"] = lambda value: quote(str(value), safe="")
    environment.filters["nl2br"] = lambda value: Markup("<br>").join(escape(value).splitlines())
    site = {**config, **metadata}

    def render(template, path, title, layout, view=None):
        target = destination / path
        home = "../" * (len(path.parts) - 1) or "./"
        if layout == "not-found":
            home = config["baseurl"].rstrip("/") + "/"
        html = environment.get_template(template).render(
            site=site,
            page={"title": title, "layout": layout, "record_id": view["record"]["id"] if view else None},
            home=home,
            view=view,
            current_year=metadata["buildDate"][:4],
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
        target.write_text(html, encoding="utf-8", newline="\n")

    # Render before copying assets so missing templates and invalid context fail explicitly.
    render("home.html", Path("index.html"), "Plan your next move", "home")
    render("404.html", Path("404.html"), "Retirement not found", "not-found")
    expected = set()
    for view in metadata["byId"].values():
        record = view["record"]
        path = Path("retirements") / quote(record["id"], safe="!~*'()") / "index.html"
        expected.add(path)
        render("retirement.html", path, record["title"], "retirement", view)

    for old in (destination / "retirements").glob("*/index.html"):
        if old.relative_to(destination) not in expected:
            old.unlink()
            if not any(old.parent.iterdir()):
                old.parent.rmdir()

    for directory in ("css", "js", "data"):
        shutil.copytree(source / "assets" / directory, destination / "assets" / directory, dirs_exist_ok=True)
    (destination / ".nojekyll").write_text("", encoding="utf-8")
    return len(expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Serve the rebuilt site at http://localhost:8000")
    arguments = parser.parse_args()
    prepare_site()
    count = build_site()
    check_site()
    print(f"Built {count} retirement pages in docs. Preview with: python -m http.server 8000 --directory docs")
    if arguments.serve:
        from functools import partial
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        with ThreadingHTTPServer(("127.0.0.1", 8000), partial(SimpleHTTPRequestHandler, directory=str(ROOT / "docs"))) as server:
            print("Serving http://localhost:8000; press Ctrl+C to stop.", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
