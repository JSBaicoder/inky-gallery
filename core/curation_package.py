import json
import shutil
from pathlib import Path

from PIL import Image

from core.curator import build_shortlist


CURATION_DIR = (
    Path.home()
    / "gallery"
    / "curation"
    / "current"
)

THUMB_SIZE = (800, 800)


def reset_curation_directory():
    if CURATION_DIR.exists():
        shutil.rmtree(CURATION_DIR)

    CURATION_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def create_thumbnail(
    source_path,
    output_path,
):
    """
    Create a full-artwork thumbnail without cropping.

    The visual curator should see the entire composition,
    not our eventual 4:3 display crop.
    """

    with Image.open(source_path) as image:
        image = image.convert("RGB")

        image.thumbnail(
            THUMB_SIZE,
            Image.Resampling.LANCZOS,
        )

        canvas = Image.new(
            "RGB",
            THUMB_SIZE,
            "white",
        )

        x = (
            THUMB_SIZE[0]
            - image.width
        ) // 2

        y = (
            THUMB_SIZE[1]
            - image.height
        ) // 2

        canvas.paste(
            image,
            (x, y),
        )

        canvas.save(
            output_path,
            format="JPEG",
            quality=90,
        )


def build_curation_package():
    reset_curation_directory()

    candidates = build_shortlist()

    manifest = []

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        source_path = Path(
            candidate["image_path"]
        )

        thumbnail_name = (
            f"{index}_"
            f"{candidate['source']}_"
            f"{candidate['source_id']}.jpg"
        )

        thumbnail_path = (
            CURATION_DIR
            / thumbnail_name
        )

        create_thumbnail(
            source_path,
            thumbnail_path,
        )

        manifest.append({
            "candidate_number": index,
            "source": candidate["source"],
            "source_id": candidate["source_id"],
            "title": candidate["title"],
            "artist": candidate["artist"],
            "date": candidate["date"],
            "medium": candidate["medium"],
            "orientation": candidate["orientation"],
            "metadata_score": candidate[
                "metadata_score"
            ],
            "metadata_notes": candidate[
                "metadata_notes"
            ],
            "source_url": candidate[
                "source_url"
            ],
            "original_image_path": str(
                source_path
            ),
            "thumbnail_path": str(
                thumbnail_path
            ),
        })

    manifest_path = (
        CURATION_DIR
        / "manifest.json"
    )

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return manifest_path, manifest


def main():
    manifest_path, manifest = (
        build_curation_package()
    )

    print(
        f"Prepared {len(manifest)} "
        "curation candidates."
    )

    print(
        f"Manifest: {manifest_path}"
    )

    for candidate in manifest:
        print(
            f"{candidate['candidate_number']}: "
            f"{candidate['title']} "
            f"({candidate['source']})"
        )

        print(
            f"   {candidate['thumbnail_path']}"
        )


if __name__ == "__main__":
    main()
