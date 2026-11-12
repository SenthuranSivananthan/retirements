"""Report review coverage or atomically apply evidence-backed five-question edits."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from .catalog import QUESTIONS, ROOT, parse_catalog
from .refresh_data import read_snapshot, write_snapshot


def review_report(catalog, limit=10):
    if type(limit) is not int or limit < 1:
        raise ValueError("Review limit must be a positive integer")
    parse_catalog(catalog)
    records = catalog["records"]
    reviewed = [record for record in records if "sourceReview" in record]
    unreviewed = [record for record in records if "sourceReview" not in record]
    eligible = unreviewed
    rechecks = sorted(reviewed, key=lambda record: (record["sourceReview"]["reviewedOn"], record["id"]))
    recheck_count = min(len(rechecks), max(1, limit // 5)) if reviewed else 0
    selected = rechecks[:recheck_count] + eligible[:limit - recheck_count]
    selected += rechecks[recheck_count:recheck_count + max(0, limit - len(selected))]
    return {
        "total": len(records), "reviewed": len(reviewed), "unreviewed": len(unreviewed),
        "enriched": sum(record["sourceReview"]["status"] == "enriched" for record in reviewed),
        "needsReview": [
            {"id": record["id"], "issues": record["sourceReview"]["issues"]} for record in reviewed
            if record["sourceReview"]["status"] == "needs-review"
        ],
        "next": [{"id": record["id"], "title": record["title"], "reviewedOn": record.get("sourceReview", {}).get("reviewedOn")}
                 for record in selected],
    }


def review_snapshot(batch, original):
    if original is None:
        raise ValueError("Cannot review a missing catalog")
    if not isinstance(batch, dict) or batch.get("catalogSha256") != hashlib.sha256(original).hexdigest():
        raise ValueError("Catalog changed since review preparation; existing snapshot preserved")
    catalog = json.loads(original)
    parse_catalog(catalog)
    updates = batch.get("reviews")
    if not isinstance(updates, list) or not updates:
        raise ValueError("A nonempty review batch is required")
    by_id = {record["id"]: record for record in catalog["records"]}
    seen = set()
    for update in updates:
        if not isinstance(update, dict) or set(update) != {"id", "summary", "questions", "sourceReview"}:
            raise ValueError("Invalid review update fields")
        identifier = update["id"]
        if not isinstance(identifier, str) or identifier not in by_id or identifier in seen:
            raise ValueError("Unknown or duplicate review ID")
        seen.add(identifier)
        record = by_id[identifier]
        questions = update["questions"]
        if not isinstance(questions, dict) or set(questions) != set(QUESTIONS):
            raise ValueError("Each review must address exactly five questions")
        review = copy.deepcopy(update["sourceReview"])
        if not isinstance(review, dict) or "originalAnnouncement" in review or "originalDeadline" in review:
            raise ValueError("Original source evidence is captured automatically, not supplied by the review")
        previous = record.get("sourceReview", {})
        if "guidanceSource" in previous and "guidanceSource" not in review:
            review["guidanceSource"] = previous["guidanceSource"]
        if "excludedReferences" in previous and "excludedReferences" not in review:
            review["excludedReferences"] = copy.deepcopy(previous["excludedReferences"])
        review["originalAnnouncement"] = previous.get("originalAnnouncement", record["questions"]["what"]["announcement"])
        review["originalDeadline"] = copy.deepcopy(previous.get("originalDeadline", {
            key: record["questions"]["deadline"][key] for key in ("date", "month")
        }))
        for section in QUESTIONS:
            changes = questions[section]
            allowed = (set(record["questions"][section]) - {"question"}) | {"html"}
            if section == "progress":
                allowed.add("tracking")
            if not isinstance(changes, dict) or set(changes) - allowed:
                raise ValueError(f"Invalid answer fields for {identifier}/{section}")
            record["questions"][section].update(copy.deepcopy(changes))
        record.update({"summary": update["summary"], "sourceReview": review})
    parse_catalog(catalog)
    return catalog


def apply_reviews(batch, output=ROOT / "data" / "retirements.json"):
    output = Path(output)
    original = read_snapshot(output)
    if original is not None:
        catalog = json.loads(original)
        parse_catalog(catalog)
        if any("manualEnrichment" in record for record in catalog["records"]):
            raise ValueError("Review automatic research through scripts.pipeline review, not the composed manual catalog")
    catalog = review_snapshot(batch, original)
    write_snapshot(catalog, output, original, operation="content review")
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--apply", type=Path, help="Evidence-backed review batch JSON; never fetches or invents answers")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be a positive integer")
    path = ROOT / "data" / "retirements.json"
    if args.apply:
        apply_reviews(json.loads(args.apply.read_text(encoding="utf-8")), path)
    snapshot = path.read_bytes()
    catalog = parse_catalog(json.loads(snapshot))
    report = review_report(catalog, args.limit)
    report["catalogSha256"] = hashlib.sha256(snapshot).hexdigest()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
