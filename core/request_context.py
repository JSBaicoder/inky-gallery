import json
import sys
from datetime import datetime
from pathlib import Path

from core.request_interpreter import interpret_request
from core.request_queue import get_next_due_request, load_queue, save_queue


CURATION_DIR = Path.home() / "gallery" / "curation" / "current"
REQUEST_CONTEXT_FILE = CURATION_DIR / "request_context.json"


def now_iso():
    return datetime.now().astimezone().isoformat()


def attach_interpretation_if_missing(request_item):
    if request_item.get("interpreted_request"):
        return request_item

    interpretation = interpret_request(request_item["request_text"])

    queue = load_queue()

    for item in queue:
        if item.get("id") == request_item.get("id"):
            item["interpreted_request"] = interpretation
            item["interpreted_at"] = now_iso()
            request_item = item
            break

    save_queue(queue)
    return request_item


def build_request_context(request_item):
    interpreted = request_item.get("interpreted_request") or {}

    return {
        "mode": "requested_artwork",
        "request_id": request_item.get("id"),
        "request_text": request_item.get("request_text"),
        "timing": request_item.get("timing"),
        "target_date": request_item.get("target_date"),
        "status": request_item.get("status"),
        "request_summary": interpreted.get("request_summary"),
        "search_terms": interpreted.get("search_terms", []),
        "start_year": interpreted.get("start_year"),
        "end_year": interpreted.get("end_year"),
        "artist": interpreted.get("artist"),
        "medium": interpreted.get("medium"),
        "culture_or_region": interpreted.get("culture_or_region"),
        "visual_preferences": interpreted.get("visual_preferences", []),
        "exclude_terms": interpreted.get("exclude_terms", []),
        "generated_at": now_iso(),
    }


def save_request_context(context):
    CURATION_DIR.mkdir(parents=True, exist_ok=True)

    with REQUEST_CONTEXT_FILE.open("w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

    return REQUEST_CONTEXT_FILE


def main():
    target_day = sys.argv[1] if len(sys.argv) > 1 else None

    request_item = get_next_due_request(target_day=target_day)

    if not request_item:
        print("No due request found.")
        return

    request_item = attach_interpretation_if_missing(request_item)

    context = build_request_context(request_item)
    path = save_request_context(context)

    print("REQUEST CONTEXT CREATED")
    print()
    print(json.dumps(context, indent=2))
    print()
    print(f"Saved to: {path}")


if __name__ == "__main__":
    main()
