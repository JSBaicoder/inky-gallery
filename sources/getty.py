import json
import random
import re
import urllib.parse
import urllib.request

from PIL import Image

from core.artwork import Artwork
from core.downloader import download_artwork
from core.eligibility import check_display_eligibility


SPARQL_URL = "https://data.getty.edu/museum/collection/sparql"

OBJECT_URL_PATTERN = re.compile(
    r"^https://data\.getty\.edu/museum/collection/object/[0-9a-f-]+$"
)

MEDIA_URL_PATTERN = re.compile(
    r"^https://data\.getty\.edu/media/image/[0-9a-f-]+$"
)

CC0_URL = "creativecommons.org/publicdomain/zero/1.0"

CANDIDATE_LIMIT = 100
IIIF_MAX_SIZE = 2400


def get_json(url, accept=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Gallery/1.0)"
    }

    if accept:
        headers["Accept"] = accept

    request = urllib.request.Request(
        url,
        headers=headers,
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def walk_dicts(value):
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def get_classification_ids(value):
    ids = []

    for item in walk_dicts(value):
        item_id = item.get("id")

        if item_id:
            ids.append(item_id)

    return ids


def discover_object_urls(limit=CANDIDATE_LIMIT):
    query = f"""
    SELECT DISTINCT ?object
    WHERE {{
        ?object ?p ?o .
        FILTER(
            REGEX(
                STR(?object),
                "^https://data\\\\.getty\\\\.edu/museum/collection/object/[0-9a-f-]+$"
            )
        )
    }}
    LIMIT {limit}
    """

    params = urllib.parse.urlencode({
        "query": query
    })

    url = f"{SPARQL_URL}?{params}"

    data = get_json(
        url,
        accept="application/sparql-results+json",
    )

    object_urls = []

    for result in data.get("results", {}).get("bindings", []):
        object_url = (
            result.get("object", {})
            .get("value")
        )

        if object_url and OBJECT_URL_PATTERN.match(object_url):
            object_urls.append(object_url)

    random.shuffle(object_urls)

    return object_urls


def get_orientation(width, height):
    ratio = width / height

    if ratio > 1.05:
        return "landscape"

    if ratio < 0.95:
        return "portrait"

    return "square"


def get_title(artwork_data):
    names = artwork_data.get("identified_by") or []

    # Prefer Getty's explicitly identified preferred/primary title.
    for name in names:
        if name.get("type") != "Name":
            continue

        label = (name.get("_label") or "").lower()

        classifications = get_classification_ids(
            name.get("classified_as") or []
        )

        is_primary = any(
            item_id.endswith("/object-title-primary")
            for item_id in classifications
        )

        if (
            is_primary
            or "preferred title" in label
        ):
            content = name.get("content")

            if content:
                return content

    # Fall back to the first usable Name.
    for name in names:
        if name.get("type") == "Name":
            content = name.get("content")

            if content:
                return content

    return artwork_data.get("_label") or "Untitled"


def get_artist(artwork_data):
    production = artwork_data.get("produced_by")

    if not production:
        return None

    artists = []

    for item in walk_dicts(production):
        carried_out_by = item.get("carried_out_by")

        if not isinstance(carried_out_by, list):
            continue

        for actor in carried_out_by:
            if not isinstance(actor, dict):
                continue

            label = actor.get("_label")

            if label and label not in artists:
                artists.append(label)

    if not artists:
        return None

    return "; ".join(artists[:3])


def get_date(artwork_data):
    production = artwork_data.get("produced_by")

    if not production:
        return None

    for item in walk_dicts(production):
        timespan = item.get("timespan")

        if not isinstance(timespan, dict):
            continue

        label = timespan.get("_label")

        if label:
            return label

    return None


def get_medium(artwork_data):
    materials = artwork_data.get("made_of") or []

    material_labels = []

    for material in materials:
        if not isinstance(material, dict):
            continue

        label = material.get("_label")

        if label and label not in material_labels:
            material_labels.append(label)

    if material_labels:
        return ", ".join(material_labels)

    # Fall back to Getty's object classification.
    for classification in artwork_data.get("classified_as") or []:
        if not isinstance(classification, dict):
            continue

        nested = classification.get("classified_as") or []

        nested_labels = [
            (item.get("_label") or "").lower()
            for item in nested
            if isinstance(item, dict)
        ]

        if any(
            "classification (category)" in label
            for label in nested_labels
        ):
            label = classification.get("_label")

            if label:
                return label

    return None


def get_main_representation(artwork_data):
    representations = artwork_data.get("representation") or []

    # Prefer Getty's explicitly labelled main view.
    for representation in representations:
        if not isinstance(representation, dict):
            continue

        label = (representation.get("_label") or "").lower()

        if (
            "main view" in label
            and representation.get("format") == "image/jpeg"
        ):
            return representation

    # Fall back to the first JPEG representation.
    for representation in representations:
        if not isinstance(representation, dict):
            continue

        if representation.get("format") == "image/jpeg":
            return representation

    return None


def get_asset_name(representation):
    for identifier in representation.get("identified_by") or []:
        if not isinstance(identifier, dict):
            continue

        label = (identifier.get("_label") or "").lower()

        if label == "asset name":
            return identifier.get("content")

        classifications = identifier.get("classified_as") or []

        for classification in classifications:
            if not isinstance(classification, dict):
                continue

            item_id = classification.get("id") or ""

            if item_id.endswith("/asset-name"):
                return identifier.get("content")

    return None


def get_media_record_url(artwork_data, asset_name):
    candidates = []

    for item in walk_dicts(artwork_data):
        item_id = item.get("id")

        if not isinstance(item_id, str):
            continue

        if not MEDIA_URL_PATTERN.match(item_id):
            continue

        if item_id not in candidates:
            candidates.append(item_id)

        if asset_name:
            for identifier in item.get("identified_by") or []:
                if not isinstance(identifier, dict):
                    continue

                if identifier.get("content") == asset_name:
                    return item_id

            label = item.get("_label") or ""

            if asset_name in label:
                return item_id

    # If Getty supplied only one media record, it is safe to use it.
    if len(candidates) == 1:
        return candidates[0]

    return None


def is_cc0_media(media_data):
    rights = media_data.get("subject_to") or []

    for item in walk_dicts(rights):
        item_id = item.get("id")

        if not isinstance(item_id, str):
            continue

        normalized = (
            item_id
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )

        if normalized == CC0_URL:
            return True

    return False


def get_iiif_image_url(media_data):
    digitally_shown_by = media_data.get("digitally_shown_by") or []

    full_resolution_url = None

    for digital_object in digitally_shown_by:
        if not isinstance(digital_object, dict):
            continue

        for access_point in digital_object.get("access_point") or []:
            if not isinstance(access_point, dict):
                continue

            url = access_point.get("id")

            if not url:
                continue

            classifications = get_classification_ids(
                access_point.get("classified_as") or []
            )

            conforms_to = access_point.get("conforms_to") or ""

            is_iiif_service = (
                "iiif.io/api/image" in conforms_to
                or any(
                    item_id.endswith("/iiif-image")
                    for item_id in classifications
                )
            )

            if is_iiif_service:
                service_url = url.rstrip("/")

                return (
                    f"{service_url}/full/"
                    f"!{IIIF_MAX_SIZE},{IIIF_MAX_SIZE}"
                    f"/0/default.jpg"
                )

            is_full_resolution = any(
                item_id.endswith("/full-resolution")
                for item_id in classifications
            )

            if is_full_resolution:
                full_resolution_url = url

    return full_resolution_url


def get_media_dimensions(media_data):
    digitally_shown_by = media_data.get("digitally_shown_by") or []

    for digital_object in digitally_shown_by:
        if not isinstance(digital_object, dict):
            continue

        width = None
        height = None

        for dimension in digital_object.get("dimension") or []:
            if not isinstance(dimension, dict):
                continue

            value = dimension.get("value")

            classifications = dimension.get("classified_as") or []

            labels = [
                (item.get("_label") or "").lower()
                for item in classifications
                if isinstance(item, dict)
            ]

            if "width" in labels:
                width = value

            if "height" in labels:
                height = value

        if width and height:
            return int(width), int(height)

    return None, None


def get_source_url(artwork_data):
    # Prefer a human-facing Getty collection URL if one exists.
    for item in walk_dicts(artwork_data):
        item_id = item.get("id")

        if not isinstance(item_id, str):
            continue

        if "getty.edu/art/collection/object/" in item_id:
            return item_id

    return artwork_data.get("id")


def create_artwork_record(artwork_data):
    representation = get_main_representation(artwork_data)

    if not representation:
        return None, None

    asset_name = get_asset_name(representation)

    media_url = get_media_record_url(
        artwork_data,
        asset_name,
    )

    if not media_url:
        return None, None

    media_data = get_json(media_url)

    # Critical Getty rule:
    # image rights must independently be CC0.
    if not is_cc0_media(media_data):
        return None, None

    image_url = get_iiif_image_url(media_data)

    if not image_url:
        return None, None

    source_id = (
        artwork_data["id"]
        .rstrip("/")
        .split("/")[-1]
    )

    original_width, original_height = get_media_dimensions(
        media_data
    )

    if not original_width or not original_height:
        return None, None

    # Check technical eligibility before downloading the image.
    candidate = Artwork(
        source="getty",
        source_id=source_id,
        title=get_title(artwork_data),
        artist=get_artist(artwork_data),
        date=get_date(artwork_data),
        medium=get_medium(artwork_data),
        image_url=image_url,
        source_url=get_source_url(artwork_data),
        license="CC0",
        width=original_width,
        height=original_height,
        orientation=get_orientation(
            original_width,
            original_height,
        ),
        display_eligible=False,
    )

    if not check_display_eligibility(candidate):
        return None, None

    image_path = download_artwork(candidate)

    with Image.open(image_path) as image:
        width, height = image.size

    artwork = Artwork(
        source="getty",
        source_id=source_id,
        title=candidate.title,
        artist=candidate.artist,
        date=candidate.date,
        medium=candidate.medium,
        image_url=image_url,
        source_url=candidate.source_url,
        license="CC0",
        width=width,
        height=height,
        orientation=get_orientation(width, height),
        display_eligible=False,
    )

    if not check_display_eligibility(artwork):
        return None, None

    artwork.display_eligible = True

    return artwork, image_path


def find_artwork():
    object_urls = discover_object_urls()

    for object_url in object_urls:
        try:
            artwork_data = get_json(object_url)

            artwork, image_path = create_artwork_record(
                artwork_data
            )

            if artwork:
                return artwork, image_path

        except Exception as error:
            print(
                f"Skipping Getty object {object_url}: {error}"
            )

    return None, None


def main():
    artwork, image_path = find_artwork()

    if artwork:
        print(json.dumps(artwork.to_dict(), indent=2))
        print(f"image_path: {image_path}")

    else:
        print("No eligible Getty artwork found.")


if __name__ == "__main__":
    main()
