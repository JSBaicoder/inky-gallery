import json
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path


GALLERY_DIR = Path.home() / "gallery"
DATA_DIR = GALLERY_DIR / "data"
QUEUE_FILE = DATA_DIR / "request_queue.json"


def now_iso():
    return datetime.now().astimezone().isoformat()


def today_str():
    return date.today().isoformat()


def ensure_queue_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not QUEUE_FILE.exists():
        save_queue([])


def load_queue():
    ensure_queue_file()

    try:
        with QUEUE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except (json.JSONDecodeError, OSError):
        return []


def save_queue(queue):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with QUEUE_FILE.open("w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)


def add_request(request_text, timing, target_date=None):
    queue = load_queue()

    if timing == "tomorrow" and not target_date:
        target_date = (date.today() + timedelta(days=1)).isoformat()

    entry = {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "request_text": request_text.strip(),
        "timing": timing,               # now / tomorrow / date
        "target_date": target_date,     # YYYY-MM-DD or None
        "status": "queued"
    }

    queue.append(entry)
    save_queue(queue)

    return entry


def get_active_queue():
    queue = load_queue()

    return [
        item for item in queue
        if item.get("status") == "queued"
    ]


def mark_request_status(request_id, status):
    queue = load_queue()

    for item in queue:
        if item.get("id") == request_id:
            item["status"] = status
            item["updated_at"] = now_iso()
            break

    save_queue(queue)


def is_due_on_date(item, target_day=None):
    if target_day is None:
        target_day = today_str()

    if item.get("status") != "queued":
        return False

    timing = item.get("timing")
    item_target_date = item.get("target_date")

    if timing == "now":
        return True

    if timing in {"tomorrow", "date"}:
        return item_target_date == target_day

    return False


def get_due_requests(target_day=None):
    queue = load_queue()

    due = [
        item for item in queue
        if is_due_on_date(item, target_day=target_day)
    ]

    due.sort(key=lambda x: x.get("created_at", ""))

    return due


def get_next_due_request(target_day=None):
    due = get_due_requests(target_day=target_day)

    if due:
        return due[0]

    return None
