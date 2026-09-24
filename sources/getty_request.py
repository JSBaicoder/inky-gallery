import random
import re
import urllib.parse

from sources.getty import (
    SPARQL_URL,
    OBJECT_URL_PATTERN,
    create_artwork_record,
    get_artist,
    get_json,
    get_medium,
    get_title,
    walk_dicts,
)


DEFAULT_DISCOVERY_LIMIT = 250
DEFAULT_REQUEST_CHECK_LIMIT = 60
MAX_SEARCH_TERMS = 3


def clean_terms(values):
    return [
        value.strip()
        for value in values
        if isinstance(value, str)
        and value.strip()
    ]


def normalize_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip().lower(),
    )


def search_variant(term):
    term = normalize_text(term)

    if term.endswith("ies") and len(term) > 3:
        return term[:-3] + "y"

    if term.endswith("s") and len(term) > 3:
        return term[:-1]

    return term


def sparql_escape(value):
    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


# --------------------------------------------------
# GETTY DATE HANDLING
# --------------------------------------------------

def get_production_timespan(artwork_data):
    production = artwork_data.get("produced_by")

    if not production:
        return None

    # Getty commonly stores produced_by as one dict,
    # but walk recursively so this remains robust.
    for item in walk_dicts(production):
        timespan = item.get("timespan")

        if isinstance(timespan, dict):
            return timespan

    return None


def get_request_date(artwork_data):
    timespan = get_production_timespan(
        artwork_data
    )

    if not timespan:
        return None

    # Getty currently provides the human-readable
    # production date inside timespan.identified_by.
    for identifier in (
        timespan.get("identified_by")
        or []
    ):
        if not isinstance(identifier, dict):
            continue

        content = identifier.get("content")

        if content:
            return content

    # Older/alternate records may provide a label.
    label = timespan.get("_label")

    if label:
        return label

    # Last fallback: construct a useful range from
    # Getty's machine-readable boundaries.
    begin = timespan.get(
        "begin_of_the_begin"
    )
    end = timespan.get(
        "end_of_the_end"
    )

    begin_year = extract_iso_year(begin)
    end_year = extract_iso_year(end)

    if (
        begin_year is not None
        and end_year is not None
    ):
        if begin_year == end_year:
            return str(begin_year)

        return (
            f"{begin_year}–{end_year}"
        )

    if begin_year is not None:
        return str(begin_year)

    if end_year is not None:
        return str(end_year)

    return None


def extract_iso_year(value):
    if not value:
        return None

    match = re.match(
        r"^(-?\d{4})",
        str(value),
    )

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def get_request_year_range(
    artwork_data,
):
    timespan = get_production_timespan(
        artwork_data
    )

    if not timespan:
        return None, None

    begin_year = extract_iso_year(
        timespan.get(
            "begin_of_the_begin"
        )
    )

    end_year = extract_iso_year(
        timespan.get(
            "end_of_the_end"
        )
    )

    return begin_year, end_year


# --------------------------------------------------
# DISCOVERY
# --------------------------------------------------

def discover_request_object_urls(
    request_context,
    limit=DEFAULT_DISCOVERY_LIMIT,
):
    terms = clean_terms(
        request_context.get(
            "search_terms",
            [],
        )
    )

    if not terms:
        return []

    object_urls = set()

    for original_term in terms[
        :MAX_SEARCH_TERMS
    ]:
        term = sparql_escape(
            search_variant(
                original_term
            )
        )

        query = f"""
        SELECT DISTINCT ?object
        WHERE {{
            ?object ?p ?value .

            FILTER(
                REGEX(
                    STR(?object),
                    "^https://data\\\\.getty\\\\.edu/museum/collection/object/[0-9a-f-]+$"
                )
            )

            {{
                FILTER(isLiteral(?value))
                FILTER(
                    CONTAINS(
                        LCASE(STR(?value)),
                        "{term}"
                    )
                )
            }}
            UNION
            {{
                ?value ?p2 ?nestedValue .

                FILTER(
                    isLiteral(?nestedValue)
                )

                FILTER(
                    CONTAINS(
                        LCASE(
                            STR(?nestedValue)
                        ),
                        "{term}"
                    )
                )
            }}
        }}
        LIMIT {limit}
        """

        params = urllib.parse.urlencode(
            {
                "query": query,
            }
        )

        url = (
            f"{SPARQL_URL}?"
            f"{params}"
        )

        try:
            data = get_json(
                url,
                accept=(
                    "application/"
                    "sparql-results+json"
                ),
            )

        except Exception as error:
            print(
                f"Getty SPARQL search for "
                f"'{original_term}' failed: "
                f"{error}"
            )
            continue

        for result in (
            data
            .get("results", {})
            .get("bindings", [])
        ):
            object_url = (
                result
                .get("object", {})
                .get("value")
            )

            if (
                object_url
                and OBJECT_URL_PATTERN.match(
                    object_url
                )
            ):
                object_urls.add(
                    object_url
                )

    object_urls = list(
        object_urls
    )

    random.shuffle(
        object_urls
    )

    print(
        f"Getty request discovery "
        f"returned "
        f"{len(object_urls)} "
        f"possible objects."
    )

    return object_urls


# --------------------------------------------------
# LOCAL FILTERING
# --------------------------------------------------

def collect_text(
    artwork_data,
):
    parts = []

    for item in walk_dicts(
        artwork_data
    ):
        for key in (
            "_label",
            "content",
        ):
            value = item.get(key)

            if (
                isinstance(value, str)
                and value.strip()
            ):
                parts.append(value)

    for value in (
        get_title(artwork_data),
        get_artist(artwork_data),
        get_request_date(
            artwork_data
        ),
        get_medium(artwork_data),
    ):
        if value:
            parts.append(
                str(value)
            )

    return normalize_text(
        " | ".join(parts)
    )


def text_matches_term(
    blob,
    term,
):
    blob = normalize_text(blob)

    original = normalize_text(term)
    variant = search_variant(term)

    if original and original in blob:
        return True

    if variant and variant in blob:
        return True

    return False


def date_matches_request(
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

    object_start, object_end = (
        get_request_year_range(
            artwork_data
        )
    )

    # If the user explicitly requested a period,
    # require Getty to provide a usable production
    # date before spending later visual-review cost.
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


def matches_request_context(
    artwork_data,
    request_context,
):
    if not date_matches_request(
        artwork_data,
        request_context,
    ):
        return False

    blob = collect_text(
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
# REQUEST CANDIDATES
#
# No Terra calls are made here.
# --------------------------------------------------

def find_request_candidates(
    request_context,
    limit=2,
    max_checks=DEFAULT_REQUEST_CHECK_LIMIT,
):
    object_urls = (
        discover_request_object_urls(
            request_context
        )
    )

    candidates = []

    print(
        f"Looking for up to "
        f"{limit} qualified Getty "
        f"candidates..."
    )

    for object_url in object_urls[
        :max_checks
    ]:
        try:
            artwork_data = get_json(
                object_url
            )

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

            # Correct the display date using the
            # request adapter's Getty date parser.
            request_date = get_request_date(
                artwork_data
            )

            if request_date:
                artwork.date = request_date

            candidates.append(
                (
                    artwork,
                    image_path,
                )
            )

            print(
                f"Getty candidate "
                f"{len(candidates)}/{limit}: "
                f"{artwork.title} "
                f"({artwork.date})"
            )

            if (
                len(candidates)
                >= limit
            ):
                break

        except Exception as error:
            print(
                f"Skipping Getty object "
                f"{object_url}: {error}"
            )

    print(
        f"Getty produced "
        f"{len(candidates)} request "
        f"candidate(s)."
    )

    return candidates


def main():
    print(
        "Getty request adapter ready. "
        "Use find_request_candidates() "
        "with a request context."
    )


if __name__ == "__main__":
    main()
