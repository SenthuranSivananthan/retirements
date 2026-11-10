"""Generate the GitHub Pages website in docs using prepared catalog metadata."""

import json
import argparse
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context
from markupsafe import Markup, escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.catalog import group_timeline, prepare_site, record_url
from scripts.check_site import check_site


@pass_context
def relative_url(context, value):
    return context["home"] + value.lstrip("/")


@contextmanager
def atomic_output(destination):
    # Replacing avoids truncating files memory-mapped by Windows diff viewers.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=Path(destination).parent, prefix=".build-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
        yield temporary
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def copy_asset(source, destination):
    with atomic_output(destination) as temporary:
        shutil.copy2(source, temporary)
    return destination


def build_site(root=ROOT):
    root = Path(root)
    source = root / "site"
    destination = root / "docs"
    config = json.loads((source / "config.json").read_text(encoding="utf-8"))
    metadata = json.loads((source / "_data" / "site.json").read_text(encoding="utf-8"))
    for identifier, view in metadata["byId"].items():
        if not identifier or identifier in {".", ".."} or view["record"]["id"] != identifier:
            raise ValueError(f"Invalid retirement ID in prepared metadata: {identifier!r}")
        record_url(view["record"])
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
    site = {
        **config, **metadata,
        "timeline": group_timeline([metadata["byId"][identifier]["record"] for identifier in metadata["initialIds"]]),
    }

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
        with atomic_output(target) as temporary:
            temporary.write_text(html, encoding="utf-8", newline="\n")

    # Render before copying assets so missing templates and invalid context fail explicitly.
    render("home.html", Path("index.html"), "Plan your next move", "home")
    render("404.html", Path("404.html"), "Retirement not found", "not-found")
    expected = set()
    for view in metadata["byId"].values():
        record = view["record"]
        path = Path(record_url(record).lstrip("/")) / "index.html"
        expected.add(path)
        render("retirement.html", path, record["title"], "retirement", view)

    retirement_root = destination / "retirements"
    for old in list(retirement_root.rglob("index.html")):
        if old.relative_to(destination) not in expected:
            old.unlink()
            parent = old.parent
            while parent != retirement_root and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent

    for directory in ("css", "js", "data"):
        shutil.copytree(source / "assets" / directory, destination / "assets" / directory, dirs_exist_ok=True, copy_function=copy_asset)
    with atomic_output(destination / ".nojekyll") as temporary:
        temporary.write_text("", encoding="utf-8")
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
