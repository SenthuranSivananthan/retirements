"""Bounded public-page retrieval and content extraction for JSON enrichment."""

import hashlib
import ipaddress
import json
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import html5lib

from .pipeline import retry_delay

MAX_BYTES = 8 * 1024 * 1024
MAX_REFERENCES = 80


class DownloadError(ValueError):
    """A URL could not supply usable public content."""


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def public_url(url, resolve=False):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443) or re.search(r"[\x00-\x20\x7f\\]", url)):
            raise ValueError("Expected a public HTTPS URL without credentials")
        host = parsed.hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError("Local destinations are not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private destinations are not allowed")
        if resolve:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
                raise ValueError("Private or unresolved destination")
        return urldefrag(url)[0]
    except (ValueError, OSError) as error:
        raise DownloadError(f"Unsafe or unresolved URL {url}: {error}") from error


class PublicRedirects(HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 2

    def redirect_request(self, request, response, code, message, headers, new_url):
        public_url(new_url, resolve=True)
        return super().redirect_request(request, response, code, message, headers, new_url)


def fetch_http(url, previous=None, force=False):
    """Return one bounded body, or metadata-only 304; never retain a cache."""
    url = public_url(url, resolve=True)
    headers = {"Accept": "text/html, text/plain, application/json", "User-Agent": "AzureRetirements/1"}
    if previous and not force and previous.get("fetchUrl") == url:
        if previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        elif previous.get("lastModified"):
            headers["If-Modified-Since"] = previous["lastModified"]
    opener = build_opener(ProxyHandler({}), PublicRedirects())
    for attempt in range(3):
        try:
            with opener.open(Request(url, headers=headers), timeout=45) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise DownloadError(f"Page exceeds {MAX_BYTES} bytes: {url}")
                return {
                    "status": response.status, "body": body,
                    "resolvedUrl": public_url(response.geturl()), "headers": dict(response.headers),
                }
        except HTTPError as error:
            try:
                if error.code == 304:
                    return {"status": 304, "headers": dict(error.headers), "resolvedUrl": url}
                if error.code not in (408, 429) and error.code < 500:
                    raise DownloadError(f"HTTP {error.code}: {url}") from error
                if attempt == 2:
                    raise DownloadError(f"HTTP {error.code} after retries: {url}") from error
                delay = retry_delay(error, attempt)
            finally:
                error.close()
            time.sleep(delay)
        except (URLError, TimeoutError, OSError) as error:
            if attempt == 2:
                raise DownloadError(f"Download failed for {url}: {error}") from error
            time.sleep(2 ** attempt)
    raise DownloadError(f"Download attempts exhausted: {url}")


def content_links(links, base):
    result = []
    for href in links:
        if not isinstance(href, str) or href.startswith("#"):
            continue
        candidate = urljoin(base, href)
        try:
            candidate = public_url(candidate)
        except DownloadError:
            continue
        path = urlsplit(candidate).path.lower()
        if any(part in path.split("/") for part in ("signin", "login", "sign-in", "logout")):
            continue
        if candidate != public_url(base) and candidate not in result:
            result.append(candidate)
    if len(result) > MAX_REFERENCES:
        raise DownloadError(f"More than {MAX_REFERENCES} content references; explicit scoping is required: {base}")
    return result


def extract_html(body, base):
    document = html5lib.parse(body, namespaceHTMLElements=False)
    title = next((node.text or "" for node in document.iter("title")), "")
    main = next(document.iter("main"), None)
    if main is None:
        main = next(document.iter("article"), document)
    links = []

    def text(node):
        if not isinstance(node.tag, str) or node.tag in {
            "script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript",
        }:
            return ""
        if node.tag == "a" and node.get("href"):
            links.append(node.get("href"))
        parts = [node.text or ""]
        for child in node:
            parts.extend((text(child), child.tail or ""))
        return "".join(parts) + ("\n" if node.tag in {"p", "div", "li", "br", "h1", "h2", "h3", "tr"} else "")

    value = re.sub(r"[ \t\r\f\v]+", " ", text(main))
    value = re.sub(r" *\n *", "\n", value)
    return title.strip(), re.sub(r"\n{3,}", "\n\n", value).strip(), content_links(links, base)


def extract_content(body, content_type, base, expected_id=None):
    if not body:
        raise DownloadError(f"Empty content: {base}")
    if expected_id is not None:
        try:
            item = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DownloadError(f"Invalid Azure Updates item: {base}") from error
        if (not isinstance(item, dict) or str(item.get("id")) != expected_id
                or not isinstance(item.get("description"), str) or "Retirements" not in item.get("tags", [])):
            raise DownloadError(f"Azure Updates response is not the exact retirement {expected_id}")
        title, text, links = extract_html(item["description"].encode(), base)
        return item.get("title") or title, text, links
    media = content_type.split(";")[0].strip().lower()
    if media in ("text/html", "application/xhtml+xml"):
        return extract_html(body, base)
    if media in ("text/plain", "text/markdown"):
        text = body.decode("utf-8-sig")
        links = re.findall(r"\[[^\]]*\]\((https://[^\s)]+)(?:\s+[^)]*)?\)", text)
        links.extend(re.findall(r"(?m)^\s*\[[^\]]+\]:\s*(https://\S+)", text))
        return "", text.strip(), content_links(links, base)
    raise DownloadError(f"Unsupported content type {content_type!r}: {base}")
