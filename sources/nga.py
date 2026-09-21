import csv
import io
import json
import random
import re
import urllib.request

from PIL import Image

from core.artwork import Artwork
from core.downloader import download_artwork
from core.eligibility import check_display_eligibility


DATA_BASE = (
    "https://raw.githubusercontent.com/"
    "NationalGalleryOfArt/opendata/main/data"
)

PUBLISHED_IMAGES_URL = f"{DATA_BASE}/published_images.csv"
OBJECTS_URL = f"{DATA_BASE}/objects.csv"

IIIF_MAX_SIZE = 2400
CANDIDATE_SAMPLE_SIZE = 100


def open_csv(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Gallery/1.0)"
        },
    )

    response = urllib.request.urlopen(
        request,
        timeout=90,
    )

    text = io.TextIOWrapper(
        response,
        encoding="utf-8-sig",
    )

    return response, csv.DictReader(text)


def get_orientation(width, height):
    ratio = width / height

    if ratio > 1.05:
        return "landscape"

    if ratio < 0.95:
        return "portrait"

    return "square"


def make_iiif_url(service_url):
    return (
        f"{service_url.rstrip('/')}/full/"
        f"!{IIIF_MAX_SIZE},{IIIF_MAX_SIZE}"
        f"/0/default.jpg"
    )


def make_source_url(object_id, title):
    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        title.lower(),
    ).strip("-")

    if slug:
        return (
            f"https://www.nga.gov/artworks/"
            f"{object_id}-{slug}"
        )

    return f"https://www.nga.gov/artworks/{object_id}"


def image_row_is_eligible(row):
    if row.get("openaccess", "").strip() != "1":
        return False

    if row.get("viewtype", "").strip().lower() != "primary":
        return False

    sequence = row.get("sequence", "").strip()

    if sequence not in {"", "0"}:
        return False

    service_url = row.get("iiifurl", "").strip()

    if not service_url:
        return False

    try:
        width = int(row.get("width") or 0)
        height = int(row.get("height") or 0)
    except ValueError:
        return False

    if width <= 0 or height <= 0:
        return False

    candidate = Artwork(
        source="nga",
        source_id=row.get("depictstmsobjectid") or "",
        title="Candidate",
        artist=None,
        date=None,
        medium=None,
        image_url=make_iiif_url(service_url),
        source_url=None,
        license="CC0",
        width=width,
        height=height,
        orientation=get_orientation(width, height),
        display_eligible=False,
    )

    return check_display_eligibility(candidate)


def sample_image_candidates(
    sample_size=CANDIDATE_SAMPLE_SIZE,
):
    """
    Reservoir-sample eligible NGA images across the entire
    published image dataset without loading the whole CSV
    into memory.
    """

    sample = []
    eligible_seen = 0

    response, reader = open_csv(PUBLISHED_IMAGES_URL)

    try:
        for row in reader:
            if not image_row_is_eligible(row):
                continue

            object_id = (
                row.get("depictstmsobjectid") or ""
            ).strip()

            if not object_id:
                continue

            eligible_seen += 1

            if len(sample) < sample_size:
                sample.append(row)
                continue

            replacement_index = random.randrange(
                eligible_seen
            )

            if replacement_index < sample_size:
                sample[replacement_index] = row

    finally:
        response.close()

    random.shuffle(sample)

    return sample


def get_object_records(object_ids):
    """
    Read objects.csv once and retain only records matching
    our sampled image candidates.
    """

    wanted = {str(object_id) for object_id in object_ids}
    records = {}

    response, reader = open_csv(OBJECTS_URL)

    try:
        for row in reader:
            object_id = (
                row.get("objectid") or ""
            ).strip()

            if object_id in wanted:
                records[object_id] = row

                if len(records) == len(wanted):
                    break

    finally:
        response.close()

    return records


def create_artwork_record(image_row, object_row):
    object_id = int(object_row["objectid"])

    title = (
        object_row.get("title")
        or "Untitled"
    ).strip()

    artist = (
        object_row.get("attribution")
        or ""
    ).strip() or None

    date = (
        object_row.get("displaydate")
        or ""
    ).strip() or None

    medium = (
        object_row.get("medium")
        or ""
    ).strip() or None

    service_url = (
        image_row.get("iiifurl")
        or ""
    ).strip()

    image_url = make_iiif_url(service_url)

    native_width = int(
        image_row.get("width") or 0
    )

    native_height = int(
        image_row.get("height") or 0
    )

    source_url = make_source_url(
        object_id,
        title,
    )

    candidate = Artwork(
        source="nga",
        source_id=object_id,
        title=title,
        artist=artist,
        date=date,
        medium=medium,
        image_url=image_url,
        source_url=source_url,
        license="CC0",
        width=native_width,
        height=native_height,
        orientation=get_orientation(
            native_width,
            native_height,
        ),
        display_eligible=False,
    )

    if not check_display_eligibility(candidate):
        return None, None

    image_path = download_artwork(candidate)

    with Image.open(image_path) as image:
        width, height = image.size

    artwork = Artwork(
        source="nga",
        source_id=object_id,
        title=title,
        artist=artist,
        date=date,
        medium=medium,
        image_url=image_url,
        source_url=source_url,
        license="CC0",
        width=width,
        height=height,
        orientation=get_orientation(
            width,
            height,
        ),
        display_eligible=False,
    )

    if not check_display_eligibility(artwork):
        return None, None

    artwork.display_eligible = True

    return artwork, image_path


def find_artwork():
    candidates = sample_image_candidates()

    if not candidates:
        return None, None

    object_ids = [
        row["depictstmsobjectid"].strip()
        for row in candidates
    ]

    object_records = get_object_records(
        object_ids
    )

    for image_row in candidates:
        object_id = (
            image_row.get("depictstmsobjectid")
            or ""
        ).strip()

        object_row = object_records.get(
            object_id
        )

        if not object_row:
            continue

        try:
            artwork, image_path = create_artwork_record(
                image_row,
                object_row,
            )

            if artwork:
                return artwork, image_path

        except Exception as error:
            print(
                f"Skipping NGA object "
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
            "No eligible NGA artwork found."
        )


if __name__ == "__main__":
    main()
