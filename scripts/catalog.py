"""Validated catalog data and shared build-time retirement calculations."""

import json
import re
import shutil
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

QUESTIONS = ("what", "actions", "impact", "deadline", "progress")
DETAIL_QUESTIONS = ("deadline", "what", "actions", "impact", "progress")
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


def learn_documentation_url(value):
    if not safe_url(value):
        return False
    parsed = urlsplit(value)
    return (
        parsed.hostname == "learn.microsoft.com" and parsed.username is None
        and not re.match(r"^/(?:[a-z]{2}-[a-z]{2}/)?(?:answers|users|training)(?:/|$)", parsed.path, re.I)
    )


def valid_source_review(record):
    tracking = record["questions"]["progress"].get("tracking")
    if "sourceReview" not in record:
        return tracking is None
    review = record["sourceReview"]
    if not isinstance(review, dict) or not record["manuallyEnriched"]:
        return False
    if (
        review.get("status") not in ("enriched", "needs-review")
        or review.get("reviewedOn") is None or not valid_date(review.get("reviewedOn"))
        or not isinstance(review.get("originalAnnouncement"), str) or not review["originalAnnouncement"].strip()
        or not isinstance(review.get("issues"), list)
        or not all(isinstance(issue, str) and issue.strip() for issue in review["issues"])
        or (review["status"] == "needs-review" and not review["issues"])
    ):
        return False
    original = review.get("originalDeadline")
    if (
        not isinstance(original, dict) or "date" not in original or not valid_date(original["date"])
        or "month" not in original or (original["month"] is not None and not isinstance(original["month"], str))
    ):
        return False
    sources = review.get("sources")
    if not isinstance(sources, list) or not sources:
        return False
    covered = set()
    for source in sources:
        if (
            not strings(source, ("title", "url", "note")) or not source["title"].strip() or not source["note"].strip()
            or not safe_url(source["url"]) or not checklist(source.get("sections"))
            or any(section not in QUESTIONS for section in source["sections"])
        ):
            return False
        covered.update(source["sections"])
    if covered != set(QUESTIONS):
        return False
    if review["status"] == "enriched" and not any(learn_documentation_url(source["url"]) for source in sources):
        return False
    if tracking is not None and (
        not isinstance(tracking, dict) or set(tracking) != {"guidance", "sourceUrl"}
        or not strings(tracking, ("guidance", "sourceUrl")) or not tracking["guidance"].strip()
        or not learn_documentation_url(tracking["sourceUrl"])
        or not any(source["url"] == tracking["sourceUrl"] and "progress" in source["sections"] for source in sources)
    ):
        return False
    guidance = review.get("guidanceSource")
    if guidance is not None and (
        not learn_documentation_url(guidance)
        or not any(source["url"] == guidance and "actions" in source["sections"] for source in sources)
    ):
        return False
    if "deadlineSource" not in review:
        return False
    deadline_source = review["deadlineSource"]
    if deadline_source is not None and (
        not learn_documentation_url(deadline_source)
        or not any(source["url"] == deadline_source and "deadline" in source["sections"] for source in sources)
    ):
        return False
    deadline = record["questions"]["deadline"]["date"]
    if deadline is not None and deadline != original["date"] and deadline_source is None:
        return False
    checks = review.get("resourceChecks")
    resources = {resource["url"] for resource in record["questions"]["actions"]["resources"]}
    if not isinstance(checks, list):
        return False
    checked = set()
    for check in checks:
        if (
            not strings(check, ("url", "detail")) or not check["detail"].strip()
            or check.get("status") not in ("read", "partial", "unavailable", "not-evidence")
            or "resolvedUrl" not in check
            or (check["resolvedUrl"] is not None and not safe_url(check["resolvedUrl"]))
            or (check["status"] == "read" and check["resolvedUrl"] is None)
            or check["url"] not in resources or check["url"] in checked
        ):
            return False
        checked.add(check["url"])
    exclusions = review.get("excludedReferences", [])
    eligible = resources | {source["url"] for source in sources} | {
        check["resolvedUrl"] for check in checks if check["resolvedUrl"] is not None
    }
    if not isinstance(exclusions, list):
        return False
    excluded = set()
    for item in exclusions:
        if (not isinstance(item, dict) or set(item) != {"url", "checkedOn", "httpStatus"}
                or not isinstance(item["url"], str) or item["url"] not in eligible or item["url"] in excluded
                or not isinstance(item["checkedOn"], str) or not valid_date(item["checkedOn"])
                or type(item["httpStatus"]) is not int or item["httpStatus"] not in (404, 410)):
            return False
        excluded.add(item["url"])
    return checked == resources


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
            if "hidden" in record and type(record["hidden"]) is not bool:
                raise ValueError("hidden flag")
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
            if not valid_source_review(record):
                raise ValueError(f"source review for {identifier}")
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


def retirement_window(window, today=None):
    current = date.fromisoformat(today or utc_today())
    if window == "retired-year":
        start, end = current.replace(month=1, day=1), current
        label = "Retired this calendar year"
        description = f"Before today, since {format_date(start.isoformat())}"
    elif window in ("6", "12", "18"):
        month = current.month - 1 + int(window)
        year, month = current.year + month // 12, month % 12 + 1
        start = current.replace(day=1)
        end = date(year, month, monthrange(year, month)[1])
        label = f"Next {window} months"
        description = f"{format_date(start.isoformat())} – {format_date(end.isoformat())}"
    else:
        raise ValueError(f"Unknown retirement window: {window}")
    return {
        "key": window, "label": label, "start": start.isoformat(), "end": end.isoformat(),
        "retired": window == "retired-year", "range": description,
    }


def in_retirement_window(deadline, window, today=None):
    bounds = retirement_window(window, today)
    value = deadline["date"]
    return value is not None and value >= bounds["start"] and (
        value < bounds["end"] if bounds["retired"] else value <= bounds["end"]
    )


def retirement_outlook(records, today=None):
    today = today or utc_today()
    return [
        {**retirement_window(window, today),
         "count": sum(in_retirement_window(record["questions"]["deadline"], window, today) for record in records)}
        for window in ("retired-year", "6", "12", "18")
    ]


def retirement_year(record):
    deadline = record["questions"]["deadline"]
    if deadline["date"]:
        return deadline["date"][:4]
    match = re.fullmatch(r"(?:" + "|".join(MONTHS) + r") (\d{4})", deadline["month"] or "")
    return match[1] if match else "unknown"


def categories_of(record):
    return list(dict.fromkeys(record.get("categories") or ["Uncategorized"]))


def services_of(record):
    return list(dict.fromkeys(record["services"] or [record["service"]]))


def sort_timeline(records):
    ordered = sorted(records, key=lambda record: (record["title"].casefold(), record["id"]))
    return sorted(ordered, key=lambda record: record["questions"]["deadline"]["date"] or "", reverse=True)


def group_timeline(records, category="", service=""):
    groups = {}
    for record in records:
        for category_name in categories_of(record):
            if category and category_name != category:
                continue
            services = groups.setdefault(category_name, {})
            for service_name in services_of(record):
                if not service or service_name == service:
                    services.setdefault(service_name, []).append(record)
    return [{
        "name": name,
        "count": len({record["id"] for entries in groups[name].values() for record in entries}),
        "services": [
            {"name": service_name, "records": sort_timeline(groups[name][service_name])}
            for service_name in sorted(groups[name], key=str.casefold)
        ],
    } for name in sorted(groups, key=str.casefold) if groups[name]]


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


def add_calendar_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def customer_lead_time(announced_on, retirement_date):
    if announced_on is None or retirement_date is None:
        return "Not calculable"
    start = date.fromisoformat(announced_on)
    end = date.fromisoformat(retirement_date)
    negative = end < start
    if negative:
        start, end = end, start
    months = (end.year - start.year) * 12 + end.month - start.month
    anchor = add_calendar_months(start, months)
    if anchor > end:
        months -= 1
        anchor = add_calendar_months(start, months)
    days = (end - anchor).days
    years, months = divmod(months, 12)
    parts = [
        f"{value} {unit}{'' if value == 1 else 's'}"
        for value, unit in ((years, "year"), (months, "month"), (days, "day"))
        if value
    ]
    duration = ", ".join(parts) or "0 days"
    return f"-{duration}" if negative else duration


def safe_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == "https" and parsed.hostname else None
    except ValueError:
        return None


def record_url(record):
    deadline = record["questions"]["deadline"]["date"]
    if not valid_date(deadline):
        raise ValueError(f"Invalid retirement date for {record['id']!r}: {deadline!r}")
    return "/retirements/" + (deadline or "unknown-date") + "/" + quote(record["id"], safe="!~*'()") + "/"


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
            "sections": [{"id": key, "question": questions[key]["question"]} for key in DETAIL_QUESTIONS],
            "year": retirement_year(record), "categories": sorted(categories_of(record), key=str.casefold),
            "url": record_url(record), "deadline": format_date(questions["deadline"]["date"]),
            "announced": format_date(record["announcedOn"]),
            "customerLeadTime": customer_lead_time(record["announcedOn"], questions["deadline"]["date"]),
            "updated": format_date(record["lastUpdatedOn"]) if record["lastUpdatedOn"] else "Not provided by source",
            "sourceUrl": safe_url(record["sourceUrl"]),
            "guidanceSource": (record.get("sourceReview") or {}).get("guidanceSource"),
            "resources": [link(value) for value in questions["actions"]["resources"] if safe_url(value["url"])],
            "support": link(questions["actions"]["support"]), "advisor": link(questions["impact"]["advisor"]),
        }
    visible = [record for record in catalog["records"] if not record.get("hidden", False)]
    navigation = [{
        "year": group["year"], "label": "Unconfirmed year" if group["year"] == "unknown" else group["year"],
        "count": len(group["records"]),
        "categories": [{
            "name": category["name"], "count": len(category["records"]),
            "records": [{"id": record["id"], "title": record["title"], "url": by_id[record["id"]]["url"]} for record in category["records"]],
        } for category in group["categories"]],
    } for group in group_retirements(visible)]
    metadata = {
        "byId": by_id, "navigation": navigation, "buildDate": today,
        "categories": sorted({category for record in visible for category in categories_of(record)}, key=str.casefold),
        "services": sorted({service for record in visible for service in services_of(record)}, key=str.casefold),
        "initialIds": [record["id"] for record in sort_timeline(visible)[:24]], "count": len(visible),
        "refreshed": format_date(timestamp(catalog["retrievedAt"]).date().isoformat()),
        "upcoming": sum(by_id[record["id"]]["status"] in {"upcoming", "soon"} for record in visible),
        "soon": sum(by_id[record["id"]]["status"] == "soon" for record in visible),
        "outlook": retirement_outlook(visible, today),
    }
    output = root / "site" / "_data" / "site.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, ensure_ascii=False) + "\n", encoding="utf-8")
    download = root / "site" / "assets" / "data" / "retirements.json"
    download.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, download)
    return metadata
