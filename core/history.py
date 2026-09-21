import json
from datetime import datetime
from pathlib import Path


HISTORY_FILE = (
    Path.home()
    / "gallery"
    / "data"
    / "history.json"
)


def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except (
        json.JSONDecodeError,
        OSError,
    ):
        pass

    return []


def save_history(history):
    HISTORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with HISTORY_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            history,
            file,
            indent=2,
            ensure_ascii=False,
        )


def artwork_key(artwork):
    return (
        f"{artwork.source}:"
        f"{artwork.source_id}"
    )


def has_been_shown(artwork):
    key = artwork_key(artwork)

    for entry in load_history():
        if entry.get("key") == key:
            return True

    return False


def record_display(artwork):
    history = load_history()

    entry = {
        "key": artwork_key(artwork),
        "displayed_at": datetime.now().astimezone().isoformat(),
        "source": artwork.source,
        "source_id": artwork.source_id,
        "title": artwork.title,
        "artist": artwork.artist,
        "date": artwork.date,
        "medium": artwork.medium,
        "orientation": artwork.orientation,
        "source_url": artwork.source_url,
    }

    history.append(entry)

    save_history(history)

    return entry
