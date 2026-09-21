import json
from datetime import datetime
from pathlib import Path

from core.curation_package import build_curation_package
from core.visual_curator import curate
from core.select_today import save_selection
from core.prepare_selected import prepare_selected


GALLERY_DIR = Path.home() / "gallery"

CURRENT_DIR = (
    GALLERY_DIR
    / "curation"
    / "current"
)

RUN_SUMMARY_FILE = (
    CURRENT_DIR
    / "run_summary.json"
)


def save_run_summary(
    manifest,
    selection,
    preparation,
):
    summary = {
        "run_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),
        "status": "prepared_not_displayed",
        "candidate_count": len(manifest),
        "selected": {
            "source": selection["source"],
            "source_id": selection["source_id"],
            "title": selection["title"],
            "artist": selection["artist"],
            "date": selection["date"],
            "medium": selection["medium"],
        },
        "preparation": {
            "method": preparation["method"],
            "crop_fraction": preparation[
                "crop_fraction"
            ],
            "prepared_image_path": preparation[
                "prepared_image_path"
            ],
            "target_width": preparation[
                "target_width"
            ],
            "target_height": preparation[
                "target_height"
            ],
        },
        "display": {
            "attempted": False,
            "successful": False,
            "reason": (
                "Physical Inky display step "
                "not enabled yet."
            ),
        },
        "history_recorded": False,
    }

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

    return summary


def run_daily():
    print(
        "1/3 Building curator shortlist..."
    )

    manifest_path, manifest = (
        build_curation_package()
    )

    if not manifest:
        raise RuntimeError(
            "No curator candidates were found."
        )

    print(
        f"    Prepared {len(manifest)} candidates."
    )

    print(
        "2/3 Asking Terra to select artwork..."
    )

    chosen, decision = curate()

    selection = save_selection(
        chosen,
        decision,
    )

    print(
        f"    Selected: "
        f"{selection['title']}"
    )

    if selection["artist"]:
        print(
            f"    Artist: "
            f"{selection['artist']}"
        )

    print(
        "3/3 Preparing 1600x1200 image..."
    )

    preparation = prepare_selected()

    print(
        f"    Method: "
        f"{preparation['method']}"
    )

    print(
        f"    Crop fraction: "
        f"{preparation['crop_fraction']}"
    )

    summary = save_run_summary(
        manifest,
        selection,
        preparation,
    )

    return (
        manifest_path,
        selection,
        preparation,
        summary,
    )


def main():
    (
        manifest_path,
        selection,
        preparation,
        summary,
    ) = run_daily()

    print(
        "\nDAILY GALLERY RUN COMPLETE\n"
    )

    print(
        f"Artwork: "
        f"{selection['title']}"
    )

    print(
        f"Source: "
        f"{selection['source']}"
    )

    print(
        f"Prepared image: "
        f"{preparation['prepared_image_path']}"
    )

    print(
        f"Manifest: "
        f"{manifest_path}"
    )

    print(
        f"Run summary: "
        f"{RUN_SUMMARY_FILE}"
    )

    print(
        "\nStatus: PREPARED, NOT DISPLAYED"
    )

    print(
        "Display history was NOT modified."
    )


if __name__ == "__main__":
    main()
