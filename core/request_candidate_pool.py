import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps

from sources.met import (
    find_request_candidates as find_met_candidates,
)

from sources.cleveland import (
    find_request_candidates as find_cleveland_candidates,
)

from sources.getty_request import (
    find_request_candidates as find_getty_candidates,
)

from sources.nga_request import (
    find_request_candidates as find_nga_candidates,
)


GALLERY_DIR = Path.home() / "gallery"

REQUEST_CONTEXT_PATH = (
    GALLERY_DIR
    / "curation"
    / "current"
    / "request_context.json"
)

POOL_DIR = (
    GALLERY_DIR
    / "curation"
    / "request_pool"
)

THUMB_DIR = (
    POOL_DIR
    / "thumbnails"
)

MANIFEST_PATH = (
    POOL_DIR
    / "manifest.json"
)

THUMB_SIZE = 512

BACKGROUND = (
    243,
    240,
    232,
)

CANDIDATES_PER_SOURCE = 2

# For broad artist requests, first try to include
# at least one painting-like work from each museum.
#
# "oil" catches media such as:
#   Oil on canvas
#   Oil on panel
#
# "painting" catches museum metadata that uses
# classification-style wording instead.
PREFERRED_ARTIST_MEDIA = (
    "oil",
    "painting",
)


def load_request_context():
    if not REQUEST_CONTEXT_PATH.exists():
        raise FileNotFoundError(
            f"Request context not found: "
            f"{REQUEST_CONTEXT_PATH}"
        )

    with REQUEST_CONTEXT_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def reset_pool_directory():
    if POOL_DIR.exists():
        shutil.rmtree(
            POOL_DIR
        )

    THUMB_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def create_thumbnail(
    image_path,
    output_path,
):
    with Image.open(
        image_path
    ) as image:
        image = image.convert("RGB")

        contained = ImageOps.contain(
            image,
            (
                THUMB_SIZE,
                THUMB_SIZE,
            ),
            method=Image.Resampling.LANCZOS,
        )

        canvas = Image.new(
            "RGB",
            (
                THUMB_SIZE,
                THUMB_SIZE,
            ),
            BACKGROUND,
        )

        x = (
            THUMB_SIZE
            - contained.width
        ) // 2

        y = (
            THUMB_SIZE
            - contained.height
        ) // 2

        canvas.paste(
            contained,
            (
                x,
                y,
            ),
        )

        canvas.save(
            output_path,
            format="JPEG",
            quality=88,
            optimize=True,
        )


def artwork_key(
    artwork,
):
    return (
        f"{artwork.source}:"
        f"{artwork.source_id}"
    )


def merge_unique_candidates(
    destination,
    candidates,
    limit,
):
    existing_keys = {
        artwork_key(artwork)
        for artwork, _ in destination
    }

    for artwork, image_path in candidates:
        key = artwork_key(
            artwork
        )

        if key in existing_keys:
            continue

        destination.append(
            (
                artwork,
                image_path,
            )
        )

        existing_keys.add(
            key
        )

        if len(destination) >= limit:
            break


def add_candidates(
    manifest_candidates,
    candidates,
):
    existing_keys = {
        item["key"]
        for item in manifest_candidates
    }

    for artwork, image_path in candidates:
        key = artwork_key(
            artwork
        )

        if key in existing_keys:
            continue

        candidate_number = (
            len(manifest_candidates)
            + 1
        )

        thumbnail_name = (
            f"candidate_"
            f"{candidate_number:02d}_"
            f"{artwork.source}.jpg"
        )

        thumbnail_path = (
            THUMB_DIR
            / thumbnail_name
        )

        create_thumbnail(
            image_path,
            thumbnail_path,
        )

        manifest_candidates.append(
            {
                "candidate_number": (
                    candidate_number
                ),
                "key": key,
                "source": (
                    artwork.source
                ),
                "source_id": (
                    artwork.source_id
                ),
                "title": (
                    artwork.title
                ),
                "artist": (
                    artwork.artist
                ),
                "date": (
                    artwork.date
                ),
                "medium": (
                    artwork.medium
                ),
                "orientation": (
                    artwork.orientation
                ),
                "width": (
                    artwork.width
                ),
                "height": (
                    artwork.height
                ),
                "image_url": (
                    artwork.image_url
                ),
                "source_url": (
                    artwork.source_url
                ),
                "original_image_path": (
                    str(image_path)
                ),
                "thumbnail_path": (
                    str(thumbnail_path)
                ),
            }
        )

        existing_keys.add(
            key
        )


def collect_source(
    name,
    function,
    context,
    **kwargs,
):
    print()
    print(
        f"=== {name.upper()} ==="
    )

    try:
        candidates = function(
            context,
            **kwargs,
        )

        print(
            f"{name}: collected "
            f"{len(candidates)} "
            f"candidate(s)."
        )

        return candidates

    except Exception as error:
        print(
            f"{name}: request "
            f"collection failed: "
            f"{error}"
        )

        return []


def collect_diverse_source(
    name,
    function,
    context,
    limit=(
        CANDIDATES_PER_SOURCE
    ),
    **kwargs,
):
    combined = []

    artist = (
        context.get("artist")
    )

    requested_medium = (
        context.get("medium")
    )

    # If the user named an artist but did not
    # specify a medium, deliberately look for
    # a painting-like candidate first.
    if (
        artist
        and not requested_medium
    ):
        for preferred_medium in (
            PREFERRED_ARTIST_MEDIA
        ):
            preferred_context = dict(
                context
            )

            preferred_context[
                "medium"
            ] = preferred_medium

            preferred = collect_source(
                (
                    f"{name} "
                    f"preferred "
                    f"{preferred_medium}"
                ),
                function,
                preferred_context,
                limit=1,
                **kwargs,
            )

            merge_unique_candidates(
                combined,
                preferred,
                limit,
            )

            if combined:
                break

    # Fill remaining slots using the user's
    # original request exactly as interpreted.
    if len(combined) < limit:
        general = collect_source(
            name,
            function,
            context,
            limit=limit,
            **kwargs,
        )

        merge_unique_candidates(
            combined,
            general,
            limit,
        )

    return combined


def build_request_candidate_pool():
    context = (
        load_request_context()
    )

    reset_pool_directory()

    all_candidates = []

    met_candidates = (
        collect_diverse_source(
            "Met",
            find_met_candidates,
            context,
        )
    )

    add_candidates(
        all_candidates,
        met_candidates,
    )

    cleveland_candidates = (
        collect_diverse_source(
            "Cleveland",
            find_cleveland_candidates,
            context,
        )
    )

    add_candidates(
        all_candidates,
        cleveland_candidates,
    )

    getty_candidates = (
        collect_diverse_source(
            "Getty",
            find_getty_candidates,
            context,
            max_checks=250,
        )
    )

    add_candidates(
        all_candidates,
        getty_candidates,
    )

    nga_candidates = (
        collect_diverse_source(
            "NGA",
            find_nga_candidates,
            context,
        )
    )

    add_candidates(
        all_candidates,
        nga_candidates,
    )

    artist_diversity_enabled = bool(
        context.get("artist")
        and not context.get("medium")
    )

    manifest = {
        "request_context": context,
        "candidate_count": (
            len(all_candidates)
        ),
        "thumbnail_size": (
            THUMB_SIZE
        ),
        "artist_medium_diversity": (
            artist_diversity_enabled
        ),
        "candidates": (
            all_candidates
        ),
    }

    with MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            indent=2,
        )

    print()
    print(
        "REQUEST CANDIDATE POOL COMPLETE"
    )

    print(
        f"Total candidates: "
        f"{len(all_candidates)}"
    )

    print(
        f"Artist medium diversity: "
        f"{artist_diversity_enabled}"
    )

    print(
        f"Manifest: "
        f"{MANIFEST_PATH}"
    )

    print(
        f"Thumbnails: "
        f"{THUMB_DIR}"
    )

    return manifest


def main():
    build_request_candidate_pool()


if __name__ == "__main__":
    main()
