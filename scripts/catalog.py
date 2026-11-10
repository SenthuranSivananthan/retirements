"""Validated catalog data and shared build-time retirement calculations."""

import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

QUESTIONS = ("what", "actions", "impact", "deadline", "progress")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
ROOT = Path(__file__).resolve().parents[1]


def utc_today():
    return datetime.now(timezone.utc).date().isoformat()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Invalid timestamp")
    value = re.sub(r"(\.\d{6})\d+", r"\1", value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def valid_date(value):
    if value is None:
        return True
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def strings(value, fields):
    return isinstance(value, dict) and all(isinstance(value.get(field), str) for field in fields)


def checklist(value):
    return isinstance(value, list) and bool(value) and all(isinstance(step, str) for step in value)


def valid_questions(value):
    if not isinstance(value, dict) or set(value) != set(QUESTIONS):
        return False
    for section in QUESTIONS:
        if not strings(value[section], ("question", "introduction")):
            return False
    what, actions, impact, deadline, progress = (value[key] for key in QUESTIONS)
    return (
        strings(what, ("announcement", "financialConsiderations"))
        and strings(actions, ("guidance", "supportGuidance"))
        and "recommendedAction" in actions and (actions["recommendedAction"] is None or isinstance(actions["recommendedAction"], str))
        and strings(actions.get("support"), ("title", "url"))
        and isinstance(actions.get("resources"), list) and all(strings(link, ("title", "url")) for link in actions["resources"])
        and strings(impact, ("guidance", "notice")) and checklist(impact.get("checklist"))
        and strings(impact.get("advisor"), ("title", "url"))
        and strings(deadline, ("dateGuidance", "consequences"))
        and "date" in deadline and valid_date(deadline["date"])
        and "month" in deadline and (deadline["month"] is None or isinstance(deadline["month"], str))
        and strings(progress, ("guidance", "storageNote")) and checklist(progress.get("checklist"))
    )


def parse_catalog(value):
    try:
        if not isinstance(value, dict) or value.get("schemaVersion") != 2 or not isinstance(value.get("source"), str):
            raise ValueError("metadata")
        timestamp(value.get("retrievedAt"))
        records = value.get("records")
        if not isinstance(records, list):
            raise ValueError("records")
        ids = set()
        for record in records:
            if not strings(record, ("id", "title", "service", "summary", "sourceUrl")):
                raise ValueError("record fields")
            identifier = record["id"]
            if not identifier or identifier in {".", ".."} or identifier in ids:
                raise ValueError("duplicate or invalid record ID")
            ids.add(identifier)
            if type(record.get("manuallyEnriched")) is not bool:
                raise ValueError("enrichment flag")
            if any(field not in record or not valid_date(record[field]) for field in ("announcedOn", "lastUpdatedOn")):
                raise ValueError("record dates")
            if not isinstance(record.get("services"), list) or not all(isinstance(service, str) for service in record["services"]):
                raise ValueError("services")
            if "categories" in record and (
                not isinstance(record["categories"], list) or not record["categories"]
                or not all(isinstance(category, str) and category.strip() for category in record["categories"])
            ):
                raise ValueError("categories")
            if not valid_questions(record.get("questions")):
                raise ValueError("questions")
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid retirement catalog: {error}") from error
    if not records:
        raise ValueError("Empty retirement catalog")
    return {key: value[key] for key in ("schemaVersion", "source", "retrievedAt", "records")}


def days_until(deadline, today=None):
    return None if deadline["date"] is None else (date.fromisoformat(deadline["date"]) - date.fromisoformat(today or utc_today())).days


def status_of(deadline, today=None):
    days = days_until(deadline, today)
    return "unknown" if days is None else "retired" if days < 0 else "soon" if days <= 90 else "upcoming"


def countdown(deadline, today=None):
    days = days_until(deadline, today)
    if days is None:
        return "Retirement date to confirm"
    if days < 0:
        return "Retired"
    if days == 0:
        return "Retires today (0 days remaining)"
    return f"{days} {'day' if days == 1 else 'days'} remaining"


def retirement_year(record):
    deadline = record["questions"]["deadline"]
    if deadline["date"]:
        return deadline["date"][:4]
    match = re.fullmatch(r"(?:" + "|".join(MONTHS) + r") (\d{4})", deadline["month"] or "")
    return match[1] if match else "unknown"


def categories_of(record):
    return list(dict.fromkeys(record.get("categories") or ["Uncategorized"]))


def group_retirements(records):
    years = {}
    for record in records:
        years.setdefault(retirement_year(record), []).append(record)
    result = []
    for year in sorted(years, key=lambda value: (value == "unknown", -int(value) if value != "unknown" else 0)):
        grouped = sorted(years[year], key=lambda record: (record["title"].casefold(), record["id"]))
        categories = {}
        for record in grouped:
            for category in categories_of(record):
                categories.setdefault(category, []).append(record)
        result.append({
            "year": year, "records": grouped,
            "categories": [{"name": category, "records": categories[category]} for category in sorted(categories, key=str.casefold)],
        })
    return result


def format_date(value):
    if value is None:
        return "Date not specified"
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {MONTHS[parsed.month - 1][:3]} {parsed.year}"


def safe_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == "https" and parsed.hostname else None
    except ValueError:
        return None


def record_url(identifier):
    return "/retirements/" + quote(identifier, safe="!~*'()") + "/"


def prepare_site(root=ROOT, today=None):
    root = Path(root)
    today = today or utc_today()
    source = root / "data" / "retirements.json"
    catalog = parse_catalog(json.loads(source.read_text(encoding="utf-8")))
    labels = {"soon": "Within 90 days", "upcoming": "Upcoming", "retired": "Retired", "unknown": "Date to confirm"}

    def link(value):
        return {**value, "url": safe_url(value["url"])}

    by_id = {}
    for record in catalog["records"]:
        questions = record["questions"]
        status = status_of(questions["deadline"], today)
        by_id[record["id"]] = {
            "record": record, "status": status, "label": labels[status], "countdown": countdown(questions["deadline"], today),
            "sections": [{"id": key, "question": questions[key]["question"]} for key in QUESTIONS],
            "year": retirement_year(record), "categories": sorted(categories_of(record), key=str.casefold),
            "url": record_url(record["id"]), "deadline": format_date(questions["deadline"]["date"]),
            "announced": format_date(record["announcedOn"]),
            "updated": format_date(record["lastUpdatedOn"]) if record["lastUpdatedOn"] else "Not provided by source",
            "sourceUrl": safe_url(record["sourceUrl"]),
            "resources": [link(value) for value in questions["actions"]["resources"] if safe_url(value["url"])],
            "support": link(questions["actions"]["support"]), "advisor": link(questions["impact"]["advisor"]),
        }
    navigation = [{
        "year": group["year"], "label": "Unconfirmed year" if group["year"] == "unknown" else group["year"],
        "count": len(group["records"]),
        "categories": [{
            "name": category["name"], "count": len(category["records"]),
            "records": [{"id": record["id"], "title": record["title"], "url": by_id[record["id"]]["url"]} for record in category["records"]],
        } for category in group["categories"]],
    } for group in group_retirements(catalog["records"])]
    newest = sorted(catalog["records"], key=lambda record: (record["title"].casefold(), record["id"]))
    newest.sort(key=lambda record: record["announcedOn"] or "", reverse=True)
    metadata = {
        "byId": by_id, "navigation": navigation, "buildDate": today,
        "services": sorted({service for record in catalog["records"] for service in record["services"]}, key=str.casefold),
        "initialIds": [record["id"] for record in newest[:24]], "count": len(by_id),
        "refreshed": format_date(timestamp(catalog["retrievedAt"]).date().isoformat()),
        "upcoming": sum(view["status"] in {"upcoming", "soon"} for view in by_id.values()),
        "soon": sum(view["status"] == "soon" for view in by_id.values()),
    }
    output = root / "site" / "_data" / "site.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, ensure_ascii=False) + "\n", encoding="utf-8")
    download = root / "site" / "assets" / "data" / "retirements.json"
    download.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, download)
    return metadata
