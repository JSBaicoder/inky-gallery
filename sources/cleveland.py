import json
import random
import urllib.parse
import urllib.request

from PIL import Image

from core.artwork import Artwork
from core.downloader import download_artwork
from core.eligibility import check_display_eligibility


SEARCH_BASE_URL = (
    "https://openaccess-api.clevelandart.org/api/artworks/"
)

SEARCH_PAGE_SIZE = 100


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Gallery/1.0)"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def build_search_url(skip, limit):
    params = urllib.parse.urlencode({
        "cc0": "true",
        "has_image": "1",
        "skip": skip,
        "limit": limit,
    })

    return f"{SEARCH_BASE_URL}?{params}"


def get_random_artwork_data():
    first_page = get_json(
        build_search_url(
            skip=0,
            limit=1,
        )
    )

    total = (
        first_page
        .get("info", {})
        .get("total", 0)
    )

    if total <= 0:
        return []

    if total <= SEARCH_PAGE_SIZE:
        random_skip = 0
        page_size = total

    else:
        max_skip = total - SEARCH_PAGE_SIZE

        random_skip = random.randint(
            0,
            max_skip,
        )

        page_size = SEARCH_PAGE_SIZE

    search_results = get_json(
        build_search_url(
            skip=random_skip,
            limit=page_size,
        )
    )

    artworks = search_results.get("data") or []

    random.shuffle(artworks)

    return artworks


def get_orientation(width, height):
    ratio = width / height

    if ratio > 1.05:
        return "landscape"

    if ratio < 0.95:
        return "portrait"

    return "square"


def create_artwork_record(artwork_data):
    image_data = artwork_data.get("images") or {}

    selected_image = (
        image_data.get("print")
        or image_data.get("web")
        or {}
    )

    image_url = selected_image.get("url")

    if not image_url:
        return None, None

    creators = artwork_data.get("creators") or []

    artist = None

    if creators:
        artist = creators[0].get("description")

    temporary_artwork = Artwork(
        source="cleveland",
        source_id=artwork_data["id"],
        title=artwork_data.get("title") or "Untitled",
        artist=artist,
        date=artwork_data.get("creation_date") or None,
        medium=artwork_data.get("technique") or None,
        image_url=image_url,
        source_url=artwork_data.get("url"),
        license="CC0",
        width=0,
        height=0,
        orientation="unknown",
        display_eligible=False,
    )

    image_path = download_artwork(
        temporary_artwork
    )

    with Image.open(image_path) as image:
        width, height = image.size

    artwork = Artwork(
        source="cleveland",
        source_id=artwork_data["id"],
        title=artwork_data.get("title") or "Untitled",
        artist=artist,
        date=artwork_data.get("creation_date") or None,
        medium=artwork_data.get("technique") or None,
        image_url=image_url,
        source_url=artwork_data.get("url"),
        license="CC0",
        width=width,
        height=height,
        orientation=get_orientation(
            width,
            height,
        ),
        display_eligible=False,
    )

    return artwork, image_path


def find_artwork():
    artworks = get_random_artwork_data()

    for artwork_data in artworks:
        try:
            artwork, image_path = (
                create_artwork_record(
                    artwork_data
                )
            )

            if (
                artwork
                and check_display_eligibility(
                    artwork
                )
            ):
                artwork.display_eligible = True

                return artwork, image_path

        except Exception as error:
            print(
                f"Skipping Cleveland object "
                f"{artwork_data.get('id')}: {error}"
            )

    return None, None


def main():
    artwork, image_path = find_artwork()

    if artwork:
        print(
            json.dumps(
                artwork.to_dict(),
                indent=2,
            )
        )

        print(
            f"image_path: {image_path}"
        )

    else:
        print(
            "No eligible Cleveland artwork found."
        )


if __name__ == "__main__":
    main()
