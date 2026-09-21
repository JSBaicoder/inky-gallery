import argparse
import json
from datetime import datetime
from pathlib import Path

from core.history import load_history, save_history


GALLERY_DIR = Path.home() / "gallery"

CURRENT_DIR = (
    GALLERY_DIR
    / "curation"
    / "current"
)

SELECTION_FILE = (
    CURRENT_DIR
    / "selection.json"
)

RUN_SUMMARY_FILE = (
    CURRENT_DIR
    / "run_summary.json"
)


def load_json(path):
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def make_artwork_key(selection):
    return (
        f"{selection['source']}:"
        f"{selection['source_id']}"
    )


def already_recorded(history, key):
    return any(
        entry.get("key") == key
        for entry in history
    )


def finalize_successful_display():
    selection = load_json(
        SELECTION_FILE
    )

    summary = load_json(
        RUN_SUMMARY_FILE
    )

    history = load_history()

    key = make_artwork_key(
        selection
    )

    if already_recorded(
        history,
        key,
    ):
        raise RuntimeError(
            f"Artwork is already in "
            f"display history: {key}"
        )

    displayed_at = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    entry = {
        "key": key,
        "displayed_at": displayed_at,
        "source": selection["source"],
        "source_id": selection["source_id"],
        "title": selection["title"],
        "artist": selection["artist"],
        "date": selection["date"],
        "medium": selection["medium"],
        "orientation": selection[
            "orientation"
        ],
        "source_url": selection[
            "source_url"
        ],
    }

    history.append(entry)

    save_history(history)

    summary["status"] = "displayed"

    summary["display"] = {
        "attempted": True,
        "successful": True,
        "completed_at": displayed_at,
    }

    summary[
        "history_recorded"
    ] = True

    with RUN_SUMMARY_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return entry


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a successful "
            "physical Inky display."
        )
    )

    parser.add_argument(
        "--confirm-success",
        action="store_true",
        help=(
            "Record the current artwork "
            "as physically displayed."
        ),
    )

    args = parser.parse_args()

    if not args.confirm_success:
        print(
            "SAFE MODE: no display success "
            "was confirmed."
        )

        print(
            "Display history was NOT modified."
        )

        print(
            "\nThis command will only write "
            "history when called with:"
        )

        print(
            "python -m core.finalize_display "
            "--confirm-success"
        )

        return

    entry = (
        finalize_successful_display()
    )

    print(
        "DISPLAY SUCCESS RECORDED\n"
    )

    print(
        json.dumps(
            entry,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
