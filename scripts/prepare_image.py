from pathlib import Path
from PIL import Image, ImageOps

INPUT_DIR = Path.home() / "gallery" / "input"
OUTPUT_DIR = Path.home() / "gallery" / "output"

TARGET_SIZE = (1600, 1200)


def prepare_image(source_path: Path) -> Path:
    image = Image.open(source_path).convert("RGB")

    # Crop to the display's 4:3 aspect ratio.
    image = ImageOps.fit(
        image,
        TARGET_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    # Save as PNG to preserve image quality.
    output_path = OUTPUT_DIR / f"{source_path.stem}_prepared.png"
    image.save(output_path, format="PNG")

    return output_path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    supported = {".jpg", ".jpeg", ".png", ".webp"}

    images = [
        path for path in INPUT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in supported
    ]

    if not images:
        print(f"No images found in {INPUT_DIR}")
        return

    for image_path in images:
        try:
            output_path = prepare_image(image_path)
            print(f"Prepared: {image_path.name} -> {output_path.name}")
        except Exception as e:
            print(f"ERROR: {image_path.name}: {e}")


if __name__ == "__main__":
    main()
