import json
import random
import urllib.parse
import urllib.request

from PIL import Image

from core.artwork import Artwork
from core.downloader import download_artwork
from core.eligibility import check_display_eligibility


SEARCH_BASE_URL = (
    "https://collectionapi.metmuseum.org/"
    "public/collection/v1.1/search"
)

OBJECT_URL = (
    "https://collectionapi.metmuseum.org/"
    "public/collection/v1/objects/{}"
)

SEARCH_PAGE_SIZE = 100
MAX_SEARCH_RESULTS = 10000


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Gallery/1.0)"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def build_search_url(offset, limit):
    params = urllib.parse.urlencode({
        "q": "painting",
        "hasImages": "true",
        "offset": offset,
        "limit": limit,
    })

    return f"{SEARCH_BASE_URL}?{params}"


def get_random_object_ids():
    # First request only determines how many results exist.
    first_page = get_json(
        build_search_url(
            offset=0,
            limit=1,
        )
    )

    total = first_page.get("total", 0)

    if total <= 0:
        return []

    # Met v1.1 permits access to the first 10,000
    # search results. Keep offset + limit within that range.
    accessible_total = min(
        total,
        MAX_SEARCH_RESULTS,
    )

    if accessible_total <= SEARCH_PAGE_SIZE:
        random_offset = 0
        page_size = accessible_total

    else:
        max_offset = (
            accessible_total
            - SEARCH_PAGE_SIZE
        )

        random_offset = random.randint(
            0,
            max_offset,
        )

        page_size = SEARCH_PAGE_SIZE

    search_results = get_json(
        build_search_url(
            offset=random_offset,
            limit=page_size,
        )
    )

    object_ids = (
        search_results.get("objectIDs")
        or []
    )

    random.shuffle(object_ids)

    return object_ids


def get_orientation(width, height):
    ratio = width / height

    if ratio > 1.05:
        return "landscape"

    if ratio < 0.95:
        return "portrait"

    return "square"


def create_artwork_record(artwork_data):
    temporary_artwork = Artwork(
        source="met",
        source_id=artwork_data["objectID"],
        title=artwork_data.get("title") or "Untitled",
        artist=artwork_data.get("artistDisplayName") or None,
        date=artwork_data.get("objectDate") or None,
        medium=artwork_data.get("medium") or None,
        image_url=artwork_data["primaryImage"],
        source_url=artwork_data.get("objectURL"),
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
        source="met",
        source_id=artwork_data["objectID"],
        title=artwork_data.get("title") or "Untitled",
        artist=artwork_data.get("artistDisplayName") or None,
        date=artwork_data.get("objectDate") or None,
        medium=artwork_data.get("medium") or None,
        image_url=artwork_data["primaryImage"],
        source_url=artwork_data.get("objectURL"),
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
    object_ids = get_random_object_ids()

    for object_id in object_ids:
        try:
            artwork_data = get_json(
                OBJECT_URL.format(object_id)
            )

            if not artwork_data.get(
                "isPublicDomain"
            ):
                continue

            if not artwork_data.get(
                "primaryImage"
            ):
                continue

            artwork, image_path = (
                create_artwork_record(
                    artwork_data
                )
            )

            if check_display_eligibility(
                artwork
            ):
                artwork.display_eligible = True

                return artwork, image_path

        except Exception as error:
            print(
                f"Skipping Met object "
                f"{object_id}: {error}"
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
            "No eligible Met artwork found."
        )


if __name__ == "__main__":
    main()
