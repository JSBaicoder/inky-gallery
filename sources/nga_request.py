import random
import re

from sources.nga import (
    DATA_BASE,
    PUBLISHED_IMAGES_URL,
    OBJECTS_URL,
    open_csv,
    image_row_is_eligible,
    create_artwork_record,
)


OBJECT_TERMS_URL = (
    f"{DATA_BASE}/objects_terms.csv"
)

MAX_METADATA_CANDIDATES = 300

PICTURE_KEYWORDS = (
    "painting",
    "drawing",
    "print",
    "photograph",
    "watercolor",
    "pastel",
    "etching",
    "engraving",
    "lithograph",
    "woodcut",
)


def normalize_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip().lower(),
    )


def clean_terms(values):
    return [
        value.strip()
        for value in values
        if isinstance(value, str)
        and value.strip()
    ]


def term_variants(term):
    term = normalize_text(term)

    variants = {term}

    if term.endswith("ies") and len(term) > 3:
        variants.add(
            term[:-3] + "y"
        )

    elif term.endswith("s") and len(term) > 3:
        variants.add(
            term[:-1]
        )

    else:
        variants.add(
            term + "s"
        )

    return {
        value
        for value in variants
        if value
    }


def text_matches_term(
    text,
    term,
):
    text = normalize_text(text)

    for variant in term_variants(
        term
    ):
        if variant in text:
            return True

    return False


# --------------------------------------------------
# SUBJECT / THEME DISCOVERY
# --------------------------------------------------

def find_subject_object_ids(
    request_context,
):
    search_terms = clean_terms(
        request_context.get(
            "search_terms",
            [],
        )
    )

    if not search_terms:
        return None

    matches_by_term = {
        term: set()
        for term in search_terms
    }

    response, reader = open_csv(
        OBJECT_TERMS_URL
    )

    try:
        for row in reader:
            term_type = normalize_text(
                row.get("termtype")
            )

            # Keyword and Theme are the fields
            # best suited to subject requests.
            if term_type not in {
                "keyword",
                "theme",
            }:
                continue

            combined = " | ".join(
                [
                    row.get("term") or "",
                    row.get(
                        "visualbrowsertheme"
                    )
                    or "",
                ]
            )

            object_id = (
                row.get("objectid")
                or ""
            ).strip()

            if not object_id:
                continue

            for search_term in search_terms:
                if text_matches_term(
                    combined,
                    search_term,
                ):
                    matches_by_term[
                        search_term
                    ].add(object_id)

    finally:
        response.close()

    # Require every requested subject term
    # to apply to the object.
    sets = list(
        matches_by_term.values()
    )

    if not sets:
        return set()

    matched_ids = set.intersection(
        *sets
    )

    print(
        f"NGA subject terms matched "
        f"{len(matched_ids)} objects."
    )

    return matched_ids


# --------------------------------------------------
# OBJECT METADATA FILTERING
# --------------------------------------------------

def parse_year(value):
    try:
        return int(
            float(
                str(value).strip()
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def year_matches_request(
    row,
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

    object_start = parse_year(
        row.get("beginyear")
    )

    object_end = parse_year(
        row.get("endyear")
    )

    if (
        object_start is None
        or object_end is None
    ):
        return False

    if (
        start_year is not None
        and object_end < start_year
    ):
        return False

    if (
        end_year is not None
        and object_start > end_year
    ):
        return False

    return True


def is_picture_like(row):
    combined = " | ".join(
        [
            row.get(
                "classification"
            )
            or "",
            row.get(
                "subclassification"
            )
            or "",
            row.get(
                "visualbrowserclassification"
            )
            or "",
            row.get("medium")
            or "",
        ]
    )

    combined = normalize_text(
        combined
    )

    return any(
        keyword in combined
        for keyword in PICTURE_KEYWORDS
    )


def build_object_blob(row):
    fields = [
        row.get("title"),
        row.get("displaydate"),
        row.get("medium"),
        row.get("attribution"),
        row.get("classification"),
        row.get("subclassification"),
        row.get(
            "visualbrowserclassification"
        ),
        row.get("portfolio"),
        row.get("series"),
    ]

    return normalize_text(
        " | ".join(
            str(value)
            for value in fields
            if value
        )
    )


def matches_metadata(
    row,
    request_context,
):
    if not year_matches_request(
        row,
        request_context,
    ):
        return False

    if not is_picture_like(row):
        return False

    blob = build_object_blob(row)

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


def get_request_object_records(
    request_context,
):
    subject_ids = (
        find_subject_object_ids(
            request_context
        )
    )

    records = {}

    response, reader = open_csv(
        OBJECTS_URL
    )

    try:
        for row in reader:
            object_id = (
                row.get("objectid")
                or ""
            ).strip()

            if not object_id:
                continue

            if (
                subject_ids is not None
                and object_id
                not in subject_ids
            ):
                continue

            if not matches_metadata(
                row,
                request_context,
            ):
                continue

            records[
                object_id
            ] = row

            if (
                len(records)
                >= MAX_METADATA_CANDIDATES
            ):
                break

    finally:
        response.close()

    print(
        f"NGA metadata filtering "
        f"produced {len(records)} "
        f"possible objects."
    )

    return records


# --------------------------------------------------
# OPEN-ACCESS IMAGE JOIN
# --------------------------------------------------

def get_image_rows(
    object_ids,
):
    wanted = set(
        str(object_id)
        for object_id in object_ids
    )

    image_rows = {}

    response, reader = open_csv(
        PUBLISHED_IMAGES_URL
    )

    try:
        for row in reader:
            object_id = (
                row.get(
                    "depictstmsobjectid"
                )
                or ""
            ).strip()

            if object_id not in wanted:
                continue

            if not image_row_is_eligible(
                row
            ):
                continue

            # Keep the first eligible primary
            # open-access image for each object.
            if object_id not in image_rows:
                image_rows[
                    object_id
                ] = row

            if (
                len(image_rows)
                == len(wanted)
            ):
                break

    finally:
        response.close()

    print(
        f"NGA found open-access "
        f"display images for "
        f"{len(image_rows)} objects."
    )

    return image_rows


# --------------------------------------------------
# REQUEST ENTRY POINT
#
# Returns metadata-qualified candidates.
# ZERO Terra calls.
# --------------------------------------------------

def find_request_candidates(
    request_context,
    limit=2,
):
    object_records = (
        get_request_object_records(
            request_context
        )
    )

    if not object_records:
        print(
            "NGA produced 0 request "
            "candidate(s)."
        )
        return []

    image_rows = get_image_rows(
        object_records.keys()
    )

    usable_ids = [
        object_id
        for object_id
        in object_records
        if object_id in image_rows
    ]

    random.shuffle(
        usable_ids
    )

    candidates = []

    print(
        f"Looking for up to "
        f"{limit} qualified NGA "
        f"candidates..."
    )

    for object_id in usable_ids:
        try:
            artwork, image_path = (
                create_artwork_record(
                    image_rows[
                        object_id
                    ],
                    object_records[
                        object_id
                    ],
                )
            )

            if not artwork:
                continue

            candidates.append(
                (
                    artwork,
                    image_path,
                )
            )

            print(
                f"NGA candidate "
                f"{len(candidates)}/"
                f"{limit}: "
                f"{artwork.title}"
            )

            if (
                len(candidates)
                >= limit
            ):
                break

        except Exception as error:
            print(
                f"Skipping NGA object "
                f"{object_id}: "
                f"{error}"
            )

    print(
        f"NGA produced "
        f"{len(candidates)} request "
        f"candidate(s)."
    )

    return candidates


def main():
    print(
        "NGA request adapter ready. "
        "Use find_request_candidates() "
        "with a request context."
    )


if __name__ == "__main__":
    main()
