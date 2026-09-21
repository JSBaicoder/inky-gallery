import json
from pathlib import Path

from core.curation_package import build_curation_package
from core.visual_curator import curate


GALLERY_DIR = Path.home() / "gallery"

CURATION_CURRENT_DIR = (
    GALLERY_DIR
    / "curation"
    / "current"
)

SELECTION_FILE = (
    CURATION_CURRENT_DIR
    / "selection.json"
)


def save_selection(chosen, decision):
    selection = {
        "chosen_candidate_number": chosen["candidate_number"],
        "source": chosen["source"],
        "source_id": chosen["source_id"],
        "title": chosen["title"],
        "artist": chosen["artist"],
        "date": chosen["date"],
        "medium": chosen["medium"],
        "orientation": chosen["orientation"],
        "metadata_score": chosen["metadata_score"],
        "metadata_notes": chosen["metadata_notes"],
        "source_url": chosen["source_url"],
        "original_image_path": chosen["original_image_path"],
        "thumbnail_path": chosen["thumbnail_path"],
        "terra_decision": decision,
    }

    with SELECTION_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            selection,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return selection


def main():
    manifest_path, manifest = build_curation_package()

    print(
        f"Prepared {len(manifest)} candidates."
    )

    print(
        f"Manifest: {manifest_path}"
    )

    chosen, decision = curate()

    selection = save_selection(
        chosen,
        decision,
    )

    print("\nTODAY'S SELECTED ARTWORK\n")

    print(
        f"Candidate: {selection['chosen_candidate_number']}"
    )
    print(f"Title: {selection['title']}")
    print(
        f"Artist: "
        f"{selection['artist'] or 'Unknown'}"
    )
    print(f"Source: {selection['source']}")
    print(
        f"Original image: "
        f"{selection['original_image_path']}"
    )
    print(
        f"Thumbnail: "
        f"{selection['thumbnail_path']}"
    )

    print("\nTERRA DECISION\n")

    print(
        json.dumps(
            selection["terra_decision"],
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nSaved selection file:")
    print(SELECTION_FILE)

    print(
        "\nNo artwork has been displayed "
        "or added to history yet."
    )


if __name__ == "__main__":
    main()
