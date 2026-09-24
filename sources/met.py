import json
import random
import re
import urllib.parse
import urllib.request
from pathlib import Path

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
REQUEST_TIMEOUT = 10
DEFAULT_REQUEST_CHECK_LIMIT = 60


PICTURE_KEYWORDS = (
    "painting",
    "drawing",
    "print",
    "photograph",
    "watercolor",
    "gouache",
    "pastel",
    "engraving",
    "etching",
    "lithograph",
    "woodcut",
    "woodblock",
    "screenprint",
    "monotype",
    "aquatint",
)


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; Gallery/1.0)"
            )
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT,
    ) as response:
        return json.load(response)


def clean_terms(values):
    return [
        value.strip()
        for value in values
        if isinstance(value, str)
        and value.strip()
    ]


def normalize_text(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(text).strip().lower(),
    )


def get_orientation(width, height):
    ratio = width / height

    if ratio > 1.05:
        return "landscape"

    if ratio < 0.95:
        return "portrait"

    return "square"


# --------------------------------------------------
# NORMAL AUTONOMOUS GALLERY SEARCH
# --------------------------------------------------

def build_normal_search_url(
    offset,
    limit,
):
    params = urllib.parse.urlencode(
        {
            "q": "painting",
            "hasImages": "true",
            "offset": offset,
            "limit": limit,
        }
    )

    return f"{SEARCH_BASE_URL}?{params}"


def get_normal_object_ids():
    first_page = get_json(
        build_normal_search_url(
            offset=0,
            limit=1,
        )
    )

    total = first_page.get("total", 0)

    if total <= 0:
        return []

    accessible_total = min(
        total,
        MAX_SEARCH_RESULTS,
    )

    if accessible_total <= SEARCH_PAGE_SIZE:
        random_offset = 0
        page_size = accessible_total
    else:
        random_offset = random.randint(
            0,
            accessible_total
            - SEARCH_PAGE_SIZE,
        )
        page_size = SEARCH_PAGE_SIZE

    results = get_json(
        build_normal_search_url(
            offset=random_offset,
            limit=page_size,
        )
    )

    object_ids = (
        results.get("objectIDs")
        or []
    )

    random.shuffle(object_ids)

    return object_ids


# --------------------------------------------------
# REQUEST SEARCH
# --------------------------------------------------

def build_request_search_params(
    request_context,
    offset,
    limit,
):
    search_terms = clean_terms(
        request_context.get(
            "search_terms",
            [],
        )
    )

    artist = request_context.get("artist")
    culture = request_context.get(
        "culture_or_region"
    )

    params = {
        "hasImages": "true",
        "offset": offset,
        "limit": limit,
    }

    if search_terms:
        params["q"] = " ".join(
            search_terms
        )
        params["tags"] = "true"

    elif artist:
        params["q"] = artist
        params["artistOrCulture"] = "true"

    elif culture:
        params["q"] = culture
        params["artistOrCulture"] = "true"

    else:
        params["q"] = "painting"

    start_year = request_context.get(
        "start_year"
    )
    end_year = request_context.get(
        "end_year"
    )

    if (
        start_year is not None
        and end_year is not None
    ):
        params["dateBegin"] = start_year
        params["dateEnd"] = end_year

    return params


def build_request_search_url(
    request_context,
    offset,
    limit,
):
    params = urllib.parse.urlencode(
        build_request_search_params(
            request_context,
            offset,
            limit,
        )
    )

    return f"{SEARCH_BASE_URL}?{params}"


def get_request_object_ids(
    request_context,
    max_checks=DEFAULT_REQUEST_CHECK_LIMIT,
):
    first_page = get_json(
        build_request_search_url(
            request_context,
            offset=0,
            limit=1,
        )
    )

    total = first_page.get(
        "total",
        0,
    )

    print(
        f"Met request search returned "
        f"{total} matches."
    )

    if total <= 0:
        return []

    accessible_total = min(
        total,
        MAX_SEARCH_RESULTS,
    )

    if accessible_total <= SEARCH_PAGE_SIZE:
        random_offset = 0
        page_size = accessible_total
    else:
        random_offset = random.randint(
            0,
            accessible_total
            - SEARCH_PAGE_SIZE,
        )
        page_size = SEARCH_PAGE_SIZE

    results = get_json(
        build_request_search_url(
            request_context,
            offset=random_offset,
            limit=page_size,
        )
    )

    object_ids = (
        results.get("objectIDs")
        or []
    )

    random.shuffle(object_ids)

    return object_ids[:max_checks]


def text_matches_term(
    blob,
    term,
):
    blob = normalize_text(blob)
    term = normalize_text(term)

    if not term:
        return True

    if term in blob:
        return True

    if (
        term.endswith("s")
        and term[:-1] in blob
    ):
        return True

    if (term + "s") in blob:
        return True

    return False


def build_artwork_text_blob(
    artwork_data,
):
    parts = []

    fields = [
        artwork_data.get("title"),
        artwork_data.get("objectName"),
        artwork_data.get("medium"),
        artwork_data.get("classification"),
        artwork_data.get("culture"),
        artwork_data.get("period"),
        artwork_data.get("dynasty"),
        artwork_data.get("reign"),
        artwork_data.get(
            "artistDisplayName"
        ),
        artwork_data.get(
            "artistDisplayBio"
        ),
        artwork_data.get("objectDate"),
    ]

    for value in fields:
        if value:
            parts.append(
                str(value)
            )

    tags = (
        artwork_data.get("tags")
        or []
    )

    for tag in tags:
        term = tag.get("term")

        if term:
            parts.append(term)

    return normalize_text(
        " | ".join(parts)
    )


def is_picture_like(
    artwork_data,
):
    combined = normalize_text(
        " | ".join(
            [
                artwork_data.get(
                    "classification"
                )
                or "",
                artwork_data.get(
                    "objectName"
                )
                or "",
                artwork_data.get(
                    "medium"
                )
                or "",
            ]
        )
    )

    return any(
        keyword in combined
        for keyword in PICTURE_KEYWORDS
    )


def year_matches_request(
    artwork_data,
    request_context,
):
    start_year = request_context.get(
        "start_year"
    )
    end_year = request_context.get(
        "end_year"
    )

    if (
        start_year is None
        and end_year is None
    ):
        return True

    object_begin = artwork_data.get(
        "objectBeginDate"
    )
    object_end = artwork_data.get(
        "objectEndDate"
    )

    if (
        object_begin is None
        or object_end is None
    ):
        return True

    if (
        start_year is not None
        and object_end < start_year
    ):
        return False

    if (
        end_year is not None
        and object_begin > end_year
    ):
        return False

    return True


def matches_request_context(
    artwork_data,
    request_context,
):
    if not is_picture_like(
        artwork_data
    ):
        return False

    if not year_matches_request(
        artwork_data,
        request_context,
    ):
        return False

    blob = build_artwork_text_blob(
        artwork_data
    )

    for term in clean_terms(
        request_context.get(
            "search_terms",
            [],
        )
    ):
        if not text_matches_term(
            blob,
            term,
        ):
            return False

    artist = request_context.get(
        "artist"
    )

    if (
        artist
        and not text_matches_term(
            blob,
            artist,
        )
    ):
        return False

    medium = request_context.get(
        "medium"
    )

    if (
        medium
        and not text_matches_term(
            blob,
            medium,
        )
    ):
        return False

    culture = request_context.get(
        "culture_or_region"
    )

    if (
        culture
        and not text_matches_term(
            blob,
            culture,
        )
    ):
        return False

    for term in clean_terms(
        request_context.get(
            "exclude_terms",
            [],
        )
    ):
        if text_matches_term(
            blob,
            term,
        ):
            return False

    return True


# --------------------------------------------------
# ARTWORK CREATION
# --------------------------------------------------

def create_artwork_record(
    artwork_data,
):
    temporary_artwork = Artwork(
        source="met",
        source_id=artwork_data[
            "objectID"
        ],
        title=(
            artwork_data.get("title")
            or "Untitled"
        ),
        artist=(
            artwork_data.get(
                "artistDisplayName"
            )
            or None
        ),
        date=(
            artwork_data.get(
                "objectDate"
            )
            or None
        ),
        medium=(
            artwork_data.get("medium")
            or None
        ),
        image_url=artwork_data[
            "primaryImage"
        ],
        source_url=artwork_data.get(
            "objectURL"
        ),
        license="CC0",
        width=0,
        height=0,
        orientation="unknown",
        display_eligible=False,
    )

    image_path = download_artwork(
        temporary_artwork
    )

    with Image.open(
        image_path
    ) as image:
        width, height = image.size

    artwork = Artwork(
        source="met",
        source_id=artwork_data[
            "objectID"
        ],
        title=(
            artwork_data.get("title")
            or "Untitled"
        ),
        artist=(
            artwork_data.get(
                "artistDisplayName"
            )
            or None
        ),
        date=(
            artwork_data.get(
                "objectDate"
            )
            or None
        ),
        medium=(
            artwork_data.get("medium")
            or None
        ),
        image_url=artwork_data[
            "primaryImage"
        ],
        source_url=artwork_data.get(
            "objectURL"
        ),
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


# --------------------------------------------------
# EXISTING NORMAL ENTRY POINT
#
# IMPORTANT:
# This deliberately ignores request_context.
# The normal daily gallery therefore continues
# behaving exactly as before.
# --------------------------------------------------

def find_artwork():
    object_ids = (
        get_normal_object_ids()
    )

    for object_id in object_ids:
        try:
            artwork_data = get_json(
                OBJECT_URL.format(
                    object_id
                )
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

                return (
                    artwork,
                    image_path,
                )

        except Exception as error:
            print(
                f"Skipping Met object "
                f"{object_id}: {error}"
            )

    return None, None


# --------------------------------------------------
# NEW REQUEST ENTRY POINT
#
# Returns several metadata-qualified candidates.
# NO Terra calls happen here.
# --------------------------------------------------

def find_request_candidates(
    request_context,
    limit=2,
    max_checks=DEFAULT_REQUEST_CHECK_LIMIT,
):
    object_ids = get_request_object_ids(
        request_context,
        max_checks=max_checks,
    )

    candidates = []

    print(
        f"Looking for up to "
        f"{limit} qualified Met candidates..."
    )

    for index, object_id in enumerate(
        object_ids,
        start=1,
    ):
        try:
            artwork_data = get_json(
                OBJECT_URL.format(
                    object_id
                )
            )

            if not artwork_data.get(
                "isPublicDomain"
            ):
                continue

            if not artwork_data.get(
                "primaryImage"
            ):
                continue

            if not matches_request_context(
                artwork_data,
                request_context,
            ):
                continue

            artwork, image_path = (
                create_artwork_record(
                    artwork_data
                )
            )

            if not check_display_eligibility(
                artwork
            ):
                continue

            artwork.display_eligible = True

            candidates.append(
                (
                    artwork,
                    image_path,
                )
            )

            print(
                f"Met candidate "
                f"{len(candidates)}/{limit}: "
                f"{artwork.title}"
            )

            if len(candidates) >= limit:
                break

        except Exception as error:
            print(
                f"Skipping Met object "
                f"{object_id}: {error}"
            )

    print(
        f"Met produced "
        f"{len(candidates)} request "
        f"candidate(s)."
    )

    return candidates


def main():
    artwork, image_path = (
        find_artwork()
    )

    if artwork:
        print(
            json.dumps(
                artwork.to_dict(),
                indent=2,
            )
        )

        print(
            f"image_path: "
            f"{image_path}"
        )

    else:
        print(
            "No eligible Met artwork found."
        )


if __name__ == "__main__":
    main()
