from pathlib import Path

from PIL import Image
from inky.auto import auto


GALLERY_DIR = Path.home() / "gallery"

PREPARED_IMAGE = (
    GALLERY_DIR
    / "curation"
    / "current"
    / "prepared.png"
)


def display_current():
    if not PREPARED_IMAGE.exists():
        raise FileNotFoundError(
            f"Prepared image not found: {PREPARED_IMAGE}"
        )

    display = auto()

    if display.resolution != (1600, 1200):
        raise RuntimeError(
            f"Unexpected Inky resolution: "
            f"{display.resolution}"
        )

    with Image.open(PREPARED_IMAGE) as image:
        image = image.convert("RGB")

        if image.size != (1600, 1200):
            raise RuntimeError(
                f"Unexpected prepared image size: "
                f"{image.size}"
            )

        print(
            "Sending prepared artwork to Inky..."
        )

        display.set_image(
            image,
            saturation=0.5,
        )

        print(
            "Refreshing display..."
        )

        display.show()

    print(
        "Inky refresh completed successfully."
    )

    return True


def main():
    display_current()

    print(
        "\nDisplay history has NOT been modified."
    )


if __name__ == "__main__":
    main()
