import json
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


GALLERY_DIR = Path.home() / "gallery"

SELECTION_FILE = (
    GALLERY_DIR
    / "curation"
    / "current"
    / "selection.json"
)

OUTPUT_DIR = (
    GALLERY_DIR
    / "curation"
    / "current"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "prepared.png"
)

PREPARATION_FILE = (
    OUTPUT_DIR
    / "preparation.json"
)

TARGET_SIZE = (1600, 1200)
TARGET_RATIO = TARGET_SIZE[0] / TARGET_SIZE[1]

MAX_CROP_FRACTION = 0.12

PAPER_BACKGROUND = (
    243,
    240,
    232,
)


def load_selection():
    with SELECTION_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def calculate_crop_fraction(
    width,
    height,
):
    source_ratio = width / height

    if source_ratio > TARGET_RATIO:
        return 1 - (
            TARGET_RATIO
            / source_ratio
        )

    if source_ratio < TARGET_RATIO:
        return 1 - (
            source_ratio
            / TARGET_RATIO
        )

    return 0.0


def prepare_with_crop(image):
    return ImageOps.fit(
        image,
        TARGET_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def prepare_with_full_artwork(image):
    fitted = ImageOps.contain(
        image,
        TARGET_SIZE,
        method=Image.Resampling.LANCZOS,
    )

    canvas = Image.new(
        "RGB",
        TARGET_SIZE,
        PAPER_BACKGROUND,
    )

    x = (
        TARGET_SIZE[0]
        - fitted.width
    ) // 2

    y = (
        TARGET_SIZE[1]
        - fitted.height
    ) // 2

    canvas.paste(
        fitted,
        (x, y),
    )

    return canvas


def enhance_for_eink(
    image,
    selection,
):
    medium = (
        selection.get("medium")
        or ""
    ).lower()

    line_art_terms = (
        "etching",
        "engraving",
        "drypoint",
        "mezzotint",
        "aquatint",
        "lithograph",
        "woodcut",
        "woodblock",
        "pen and ink",
    )

    is_line_art = any(
        term in medium
        for term in line_art_terms
    )

    if is_line_art:
        image = ImageOps.autocontrast(
            image,
            cutoff=1,
        )

        image = (
            ImageEnhance.Contrast(
                image
            ).enhance(1.18)
        )

        image = (
            ImageEnhance.Sharpness(
                image
            ).enhance(1.35)
        )

        enhancement_mode = (
            "line_art"
        )

    else:
        image = ImageOps.autocontrast(
            image,
            cutoff=0.5,
        )

        image = (
            ImageEnhance.Contrast(
                image
            ).enhance(1.08)
        )

        image = (
            ImageEnhance.Sharpness(
                image
            ).enhance(1.12)
        )

        enhancement_mode = (
            "general"
        )

    return image, enhancement_mode


def prepare_selected():
    selection = load_selection()

    source_path = Path(
        selection[
            "original_image_path"
        ]
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"Selected image not found: "
            f"{source_path}"
        )

    with Image.open(
        source_path
    ) as image:
        image = image.convert("RGB")

        source_width = image.width
        source_height = image.height

        crop_fraction = (
            calculate_crop_fraction(
                source_width,
                source_height,
            )
        )

        if (
            crop_fraction
            <= MAX_CROP_FRACTION
        ):
            method = "crop_to_fill"

            prepared = (
                prepare_with_crop(
                    image
                )
            )

        else:
            method = (
                "preserve_full_artwork"
            )

            prepared = (
                prepare_with_full_artwork(
                    image
                )
            )

        (
            prepared,
            enhancement_mode,
        ) = enhance_for_eink(
            prepared,
            selection,
        )

    prepared.save(
        OUTPUT_FILE,
        format="PNG",
    )

    preparation = {
        "source": (
            selection["source"]
        ),
        "source_id": (
            selection["source_id"]
        ),
        "title": (
            selection["title"]
        ),
        "artist": (
            selection["artist"]
        ),
        "original_image_path": (
            str(source_path)
        ),
        "prepared_image_path": (
            str(OUTPUT_FILE)
        ),
        "source_width": (
            source_width
        ),
        "source_height": (
            source_height
        ),
        "target_width": (
            TARGET_SIZE[0]
        ),
        "target_height": (
            TARGET_SIZE[1]
        ),
        "crop_fraction": round(
            crop_fraction,
            4,
        ),
        "method": method,
        "eink_enhancement": (
            enhancement_mode
        ),
    }

    with PREPARATION_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            preparation,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return preparation


def main():
    preparation = (
        prepare_selected()
    )

    print()
    print("PREPARED ARTWORK")
    print()

    print(
        json.dumps(
            preparation,
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print(
        "Artwork has NOT been "
        "added to display history."
    )


if __name__ == "__main__":
    main()
