from pathlib import Path

import urllib.request

from .artwork import Artwork


INPUT_DIR = Path.home() / "gallery" / "input"


def download_artwork(artwork: Artwork) -> Path:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    extension = ".jpg"
    image_path = INPUT_DIR / f"{artwork.source}_{artwork.source_id}{extension}"

    request = urllib.request.Request(
        artwork.image_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Gallery/1.0)"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        image_path.write_bytes(response.read())

    return image_path
