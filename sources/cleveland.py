import json
import random
import re
import urllib.parse
import urllib.request

from PIL import Image

from core.artwork import Artwork
from core.downloader import download_artwork
from core.eligibility import check_display_eligibility


SEARCH_BASE_URL = (
    "https://openaccess-api.clevelandart.org/"
    "api/artworks/"
)

SEARCH_PAGE_SIZE = 100
REQUEST_TIMEOUT = 10
DEFAULT_REQUEST_CHECK_LIMIT = 60

PICTURE_TYPES = (
    "painting",
    "drawing",
    "print",
    "photograph",
    "photography",
    "watercolor",
    "manuscript",
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

def build_search_url(skip, limit):
    params = urllib.parse.urlencode(
        {
            "cc0": "true",
            "has_image": "1",
            "skip": skip,
            "limit": limit,
        }
    )

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
        max_skip = (
            total
            - SEARCH_PAGE_SIZE
        )

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

    artworks = (
        search_results.get("data")
        or []
    )

    random.shuffle(artworks)

    return artworks


# --------------------------------------------------
# REQUEST SEARCH
# --------------------------------------------------

def build_request_params(
    request_context,
    skip,
    limit,
):
    params = {
        "cc0": "true",
        "has_image": "1",
        "skip": skip,
        "limit": limit,
    }

    search_terms = clean_terms(
        request_context.get(
            "search_terms",
            [],
        )
    )

    if search_terms:
        params["q"] = " ".join(
            search_terms
        )

    artist = request_context.get(
        "artist"
    )

    if artist:
        params["artists"] = artist

    culture = request_context.get(
        "culture_or_region"
    )

    if culture:
        params["culture"] = culture

    medium = request_context.get(
        "medium"
    )

    if medium:
        params["medium"] = medium

    start_year = request_context.get(
        "start_year"
    )

    end_year = request_context.get(
        "end_year"
    )

    # API semantics are "after" and "before",
    # so use one year outside the desired
    # inclusive range.
    if start_year is not None:
        params["created_after"] = (
            start_year - 1
        )

    if end_year is not None:
        params["created_before"] = (
            end_year + 1
        )

    return params


def build_request_search_url(
    request_context,
    skip,
    limit,
):
    params = urllib.parse.urlencode(
        build_request_params(
            request_context,
            skip,
            limit,
        )
    )

    return f"{SEARCH_BASE_URL}?{params}"


def get_request_artwork_data(
    request_context,
    max_checks=DEFAULT_REQUEST_CHECK_LIMIT,
):
    first_page = get_json(
        build_request_search_url(
            request_context,
            skip=0,
            limit=1,
        )
    )

    total = (
        first_page
        .get("info", {})
        .get("total", 0)
    )

    print(
        f"Cleveland request search "
        f"returned {total} matches."
    )

    if total <= 0:
        return []

    if total <= SEARCH_PAGE_SIZE:
        random_skip = 0
        page_size = total
    else:
        max_skip = (
            total
            - SEARCH_PAGE_SIZE
        )

        random_skip = random.randint(
            0,
            max_skip,
        )

        page_size = SEARCH_PAGE_SIZE

    results = get_json(
        build_request_search_url(
            request_context,
            skip=random_skip,
            limit=page_size,
        )
    )

    artworks = (
        results.get("data")
        or []
    )

    random.shuffle(artworks)

    return artworks[:max_checks]


def build_artwork_text_blob(
    artwork_data,
):
    parts = []

    simple_fields = [
        artwork_data.get("title"),
        artwork_data.get("tombstone"),
        artwork_data.get("description"),
        artwork_data.get("technique"),
        artwork_data.get("type"),
        artwork_data.get("department"),
        artwork_data.get("collection"),
        artwork_data.get(
            "creation_date"
        ),
    ]

    for value in simple_fields:
        if value:
            parts.append(str(value))

    for culture in (
        artwork_data.get("culture")
        or []
    ):
        if culture:
            parts.append(str(culture))

    for creator in (
        artwork_data.get("creators")
        or []
    ):
        if creator.get("description"):
            parts.append(
                creator["description"]
            )

        if creator.get("biography"):
            parts.append(
                creator["biography"]
            )

    return normalize_text(
        " | ".join(parts)
    )


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


def is_picture_like(
    artwork_data,
):
    artwork_type = normalize_text(
        artwork_data.get("type")
    )

    collection = normalize_text(
        artwork_data.get("collection")
    )

    technique = normalize_text(
        artwork_data.get("technique")
    )

    combined = " | ".join(
        [
            artwork_type,
            collection,
            technique,
        ]
    )

    return any(
        picture_type in combined
        for picture_type in PICTURE_TYPES
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

    earliest = artwork_data.get(
        "creation_date_earliest"
    )

    latest = artwork_data.get(
        "creation_date_latest"
    )

    if (
        earliest is None
        or latest is None
    ):
        return True

    if (
        start_year is not None
        and latest < start_year
    ):
        return False

    if (
        end_year is not None
        and earliest > end_year
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
    image_data = (
        artwork_data.get("images")
        or {}
    )

    selected_image = (
        image_data.get("print")
        or image_data.get("web")
        or {}
    )

    image_url = selected_image.get(
        "url"
    )

    if not image_url:
        return None, None

    creators = (
        artwork_data.get("creators")
        or []
    )

    artist = None

    if creators:
        artist = creators[0].get(
            "description"
        )

    temporary_artwork = Artwork(
        source="cleveland",
        source_id=artwork_data["id"],
        title=(
            artwork_data.get("title")
            or "Untitled"
        ),
        artist=artist,
        date=(
            artwork_data.get(
                "creation_date"
            )
            or None
        ),
        medium=(
            artwork_data.get(
                "technique"
            )
            or None
        ),
        image_url=image_url,
        source_url=artwork_data.get(
            "url"
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
        source="cleveland",
        source_id=artwork_data["id"],
        title=(
            artwork_data.get("title")
            or "Untitled"
        ),
        artist=artist,
        date=(
            artwork_data.get(
                "creation_date"
            )
            or None
        ),
        medium=(
            artwork_data.get(
                "technique"
            )
            or None
        ),
        image_url=image_url,
        source_url=artwork_data.get(
            "url"
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
# Request context is deliberately ignored here.
# --------------------------------------------------

def find_artwork():
    artworks = (
        get_random_artwork_data()
    )

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

                return (
                    artwork,
                    image_path,
                )

        except Exception as error:
            print(
                f"Skipping Cleveland object "
                f"{artwork_data.get('id')}: "
                f"{error}"
            )

    return None, None


# --------------------------------------------------
# NEW REQUEST ENTRY POINT
#
# Returns metadata-qualified candidates only.
# Makes ZERO Terra calls.
# --------------------------------------------------

def find_request_candidates(
    request_context,
    limit=2,
    max_checks=DEFAULT_REQUEST_CHECK_LIMIT,
):
    artworks = get_request_artwork_data(
        request_context,
        max_checks=max_checks,
    )

    candidates = []

    print(
        f"Looking for up to "
        f"{limit} qualified Cleveland "
        f"candidates..."
    )

    for artwork_data in artworks:
        try:
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

            if not artwork:
                continue

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
                f"Cleveland candidate "
                f"{len(candidates)}/{limit}: "
                f"{artwork.title}"
            )

            if len(candidates) >= limit:
                break

        except Exception as error:
            print(
                f"Skipping Cleveland object "
                f"{artwork_data.get('id')}: "
                f"{error}"
            )

    print(
        f"Cleveland produced "
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
            f"image_path: {image_path}"
        )

    else:
        print(
            "No eligible Cleveland "
            "artwork found."
        )


if __name__ == "__main__":
    main()
