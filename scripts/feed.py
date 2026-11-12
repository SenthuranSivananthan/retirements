"""Read Microsoft's complete retirement feed without inventing exact deadlines."""

import re
import time
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen
import json

import html5lib

from .catalog import MONTHS, safe_url, timestamp

ENDPOINT = "https://www.microsoft.com/releasecommunications/api/v2/azure"


def read_announcement(html):
    links = {}

    def text(node):
        if not isinstance(node.tag, str) or node.tag in {"script", "style", "iframe"}:
            return ""
        content = re.sub(r"\s+", " ", node.text or "")
        for child in node:
            content += text(child) + re.sub(r"\s+", " ", child.tail or "")
        if node.tag == "a" and node.get("href") is not None:
            try:
                url = urljoin("https://azure.microsoft.com", node.get("href"))
            except ValueError:
                url = None
            if safe_url(url):
                links[url] = {"title": content.strip(), "url": url}
        return content + ("\n" if node.tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr"} else "")

    details = text(html5lib.parseFragment(html, namespaceHTMLElements=False))
    details = re.sub(r"[ \t\u00a0]+", " ", details)
    details = re.sub(r" *\n *", "\n", details)
    return {"details": re.sub(r"\n{3,}", "\n\n", details).strip(), "links": list(links.values())}


def title_date(title):
    dates = set()

    def add(year, month, day):
        try:
            dates.add(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            return

    pattern = "|".join(MONTHS)
    for month, day, year in re.findall(rf"\b({pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b", title, re.I):
        add(year, next(index for index, value in enumerate(MONTHS, 1) if value.lower() == month.lower()), day)
    for day, month, year in re.findall(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({pattern})[,]?\s+(20\d{{2}})\b", title, re.I):
        add(year, next(index for index, value in enumerate(MONTHS, 1) if value.lower() == month.lower()), day)
    for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b", title):
        context = r"\b(?:on|by|after|from|retire[sd]?|retiring|ends?|ending|deadline(?:\s+is)?)\s*[:(]?\s*$"
        if re.search(context, title[:match.start()], re.I) and not re.match(r"-(?:preview|ga)\b", title[match.end():], re.I):
            add(*match.groups())
    return next(iter(dates)) if len(dates) == 1 else None


def normalize(item):
    if (not isinstance(item, dict) or not item.get("id") or not isinstance(item.get("title"), str)
            or not isinstance(item.get("description"), str) or not isinstance(item.get("tags"), list)
            or "Retirements" not in item["tags"]):
        raise ValueError("Invalid retirement announcement")
    announcement = read_announcement(item["description"])
    details = announcement["details"]
    actions = re.search(
        r"(?:^|\n)(?:recommended actions?|required actions?|action required|what you need to do)[: ]*\n"
        r"([\s\S]*?)(?=\n(?:help and support|more information|learn more)[: ]*(?:\n|$)|$)", details, re.I,
    )
    services = [value for value in item.get("products", []) if isinstance(value, str) and value.strip()] if isinstance(item.get("products"), list) else []
    services = services or ["Azure platform"]
    categories = [value.strip() for value in item.get("productCategories", []) if isinstance(value, str) and value.strip()] if isinstance(item.get("productCategories"), list) else []
    categories = list(dict.fromkeys(categories)) or ["Uncategorized"]
    availability = next((value for value in (item.get("availabilities") or []) if isinstance(value, dict) and value.get("ring") == "Retirement"), None)
    month = f'{availability["month"]} {availability["year"]}' if availability and type(availability.get("year")) is int and availability.get("month") in MONTHS else None
    announced = item.get("created")
    announced = announced[:10] if isinstance(announced, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", announced) else None
    modified = item.get("modified")
    updated = None
    if modified is not None:
        try:
            if not isinstance(modified, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", modified):
                raise ValueError("timestamp format")
            updated = timestamp(modified).date().isoformat()
        except ValueError as error:
            raise ValueError("Invalid announcement modified timestamp") from error
    deadline = title_date(item["title"])
    service = " · ".join(services)
    summary = re.sub(r"\s+\S*$", "", details[:237]) + "…" if len(details) > 240 else details
    return {
        "id": str(item["id"]), "title": item["title"].strip(), "services": services, "categories": categories,
        "service": service, "announcedOn": announced, "lastUpdatedOn": updated, "hidden": False,
        "summary": summary, "sourceUrl": "https://azure.microsoft.com/updates?id=" + quote(str(item["id"]), safe="!~*'()"),
        "questions": {
            "what": {
                "question": "What is changing?",
                "introduction": "The change and what it means, including technical and financial considerations.",
                "announcement": details or summary,
                "financialConsiderations": "The text above is from Microsoft’s announcement. Pricing and financial impact are workload-specific; review replacement-service pricing and your agreements before migrating.",
            },
            "actions": {
                "question": "What do I need to do?",
                "introduction": "Required actions, options, and available support.",
                "recommendedAction": actions[1].strip() or None if actions else None,
                "guidance": "Use the official announcement for service-specific migration instructions and replacement options. Inventory dependencies, test the recommended replacement, and plan a validated rollout.",
                "resources": announcement["links"],
                "supportGuidance": "For help with your specific environment, contact your Microsoft account team or Azure support.",
                "support": {"title": "Azure support", "url": "https://azure.microsoft.com/support/create-ticket/"},
            },
            "impact": {
                "question": "Where, and how much, am I impacted?",
                "introduction": "Your affected environments, resources, and users.",
                "guidance": f"This announcement concerns {service}. Compare the versions, regions, configurations, and exceptions in the announcement with your inventory.",
                "checklist": [
                    "Check every subscription and environment, including development, test, and production.",
                    "Identify dependent applications, users, and resource owners.",
                    "Estimate migration effort, downtime risk, and replacement-service costs.",
                ],
                "notice": "No tenant access. This directory cannot determine whether your resources are affected. Use Azure Advisor service retirements alongside your inventory and the official guidance. Advisor coverage may vary by service.",
                "advisor": {"title": "Azure Advisor service retirements", "url": "https://portal.azure.com/#view/Microsoft_Azure_Expert/AdvisorMenuBlade/~/serviceRetirement"},
            },
            "deadline": {
                "question": "What is the deadline?", "introduction": "Key dates and the consequences of not acting.",
                "date": deadline, "month": month,
                "dateGuidance": (
                    "This date is extracted from the announcement title. Check the full announcement for phased deadlines, extensions, and exceptions."
                    if deadline else "An unambiguous exact date could not be extracted from the announcement title."
                    + (f" The source lists {month} as the retirement month." if month else "")
                    + " Review the official announcement for all applicable dates."
                ),
                "consequences": "After the applicable deadline, support or service availability may change. The exact consequences are service-specific; verify them in the announcement and plan to finish your migration ahead of time.",
            },
            "progress": {
                "question": "How can I track progress?", "introduction": "What work remains, and what needs attention.",
                "guidance": "Use this planning checklist as a starting point. Record resource-level owners, target dates, blockers, and evidence in your team’s tracking system.",
                "checklist": [
                    "Identify affected resources, subscriptions, and owners",
                    "Review the official migration guidance and estimate cost changes",
                    "Test the replacement and agree a migration plan",
                    "Complete migration and validate production workloads",
                ],
                "storageNote": "Checklist progress is saved only in this browser, not in Azure or a shared team system. Clearing browser data removes it.",
            },
        },
    }


def record_map(records):
    if not isinstance(records, list):
        raise ValueError("Invalid catalog records; existing snapshot preserved")
    result = {}
    for record in records:
        if (not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]
                or "manuallyEnriched" in record
                or ("hidden" in record and type(record["hidden"]) is not bool) or record["id"] in result):
            raise ValueError("Invalid record ID, deprecated manual flag, hidden flag, or duplicate ID; existing snapshot preserved")
        result[record["id"]] = record
    return result


def merge_retirements(fetched, existing):
    previous = record_map(existing)
    merged = record_map(fetched)
    for identifier, record in merged.items():
        if identifier in previous and "hidden" in previous[identifier]:
            merged[identifier] = {**record, "hidden": previous[identifier]["hidden"]}
    return [merged[identifier] for identifier in sorted(merged)]


def fetch_page(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            if attempt == 2 or (error.code != 429 and error.code < 500):
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(attempt + 1)


def fetch_retirements(fetcher=fetch_page):
    records = {}
    skip = 0
    expected = None
    while expected is None or skip < expected:
        params = urlencode({"$count": "true", "$top": "100", "$skip": str(skip), "$filter": "tags/any(f:f eq 'Retirements')", "$orderby": "id asc"})
        data = fetcher(ENDPOINT + "?" + params)
        count = data.get("@odata.count") if isinstance(data, dict) else None
        if (not isinstance(data, dict) or not isinstance(data.get("value"), list) or type(count) is not int
                or count <= 0 or (expected is not None and count != expected)):
            raise ValueError("Azure feed schema or count changed; existing snapshot preserved")
        expected = count
        if not data["value"]:
            raise ValueError("Azure feed ended before all announcements were fetched")
        for item in data["value"]:
            record = normalize(item)
            records[record["id"]] = record
        skip += len(data["value"])
    if len(records) != expected or skip != expected:
        raise ValueError("Azure feed contains duplicates or changed during pagination; retry refresh")
    return [records[identifier] for identifier in sorted(records)]
