import json
import os
import re
from pathlib import Path

from openai import OpenAI


MODEL = "gpt-5.6-terra"

ENV_FILE = (
    Path.home()
    / ".config"
    / "inky"
    / "openai.env"
)


def load_openai_key():
    if os.environ.get(
        "OPENAI_API_KEY"
    ):
        return

    if not ENV_FILE.exists():
        raise RuntimeError(
            f"OpenAI environment file "
            f"not found: {ENV_FILE}"
        )

    for raw_line in (
        ENV_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
    ):
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split(
            "=",
            1,
        )

        if (
            key.strip()
            == "OPENAI_API_KEY"
        ):
            os.environ[
                "OPENAI_API_KEY"
            ] = (
                value
                .strip()
                .strip('"')
                .strip("'")
            )

            return

    raise RuntimeError(
        "OPENAI_API_KEY was not "
        "found in the environment file."
    )


def normalize_interpretation(
    request_text,
    result,
):
    """
    Apply deterministic safeguards after
    Terra interpretation.

    These rules only clarify explicit user
    wording. They do not invent new criteria.
    """

    text = request_text.lower()

    artist = (
        result.get("artist")
        or ""
    ).strip()

    # Avoid confusing Rembrandt van Rijn
    # with artists whose names merely contain
    # "Rembrandt", such as Rembrandt Peale.
    if artist.lower() == "rembrandt":
        result[
            "artist"
        ] = "Rembrandt van Rijn"

    # Explicit medium words should never be
    # lost during interpretation.
    #
    # Keep broad "painting" language broad.
    # Museum-specific matching can decide
    # which painting media qualify.
    if (
        re.search(
            r"\bpaintings?\b",
            text,
        )
        and not result.get("medium")
    ):
        result[
            "medium"
        ] = "painting"

    if (
        re.search(
            r"\boil paintings?\b",
            text,
        )
    ):
        result[
            "medium"
        ] = "oil"

    if (
        re.search(
            r"\bwatercolou?r\b",
            text,
        )
    ):
        result[
            "medium"
        ] = "watercolor"

    if (
        re.search(
            r"\betchings?\b",
            text,
        )
    ):
        result[
            "medium"
        ] = "etching"

    if (
        re.search(
            r"\bengravings?\b",
            text,
        )
    ):
        result[
            "medium"
        ] = "engraving"

    if (
        re.search(
            r"\bdrawings?\b",
            text,
        )
    ):
        result[
            "medium"
        ] = "drawing"

    if (
        re.search(
            r"\bphotographs?\b|\bphotos?\b",
            text,
        )
    ):
        result[
            "medium"
        ] = "photograph"

    return result


def interpret_request(
    request_text,
):
    load_openai_key()

    client = OpenAI()

    schema = {
        "type": "object",
        "properties": {
            "search_terms": {
                "type": "array",
                "items": {
                    "type": "string"
                },
            },
            "start_year": {
                "type": [
                    "integer",
                    "null",
                ],
            },
            "end_year": {
                "type": [
                    "integer",
                    "null",
                ],
            },
            "artist": {
                "type": [
                    "string",
                    "null",
                ],
            },
            "medium": {
                "type": [
                    "string",
                    "null",
                ],
            },
            "culture_or_region": {
                "type": [
                    "string",
                    "null",
                ],
            },
            "visual_preferences": {
                "type": "array",
                "items": {
                    "type": "string"
                },
            },
            "exclude_terms": {
                "type": "array",
                "items": {
                    "type": "string"
                },
            },
            "request_summary": {
                "type": "string",
            },
        },
        "required": [
            "search_terms",
            "start_year",
            "end_year",
            "artist",
            "medium",
            "culture_or_region",
            "visual_preferences",
            "exclude_terms",
            "request_summary",
        ],
        "additionalProperties": False,
    }

    instructions = """
You interpret natural-language artwork requests for a museum art frame.

Convert the user's request into conservative structured search criteria.

Rules:

- Do not invent requirements that the user did not request.

- Preserve every explicit factual constraint the user gives.

- Separate searchable subject matter from visual preferences.

- Convert centuries or decades into numeric year ranges.

- "1700s" means 1700 through 1799 unless context clearly says otherwise.

- A subject such as trees, clouds, birds, mountains, boats, or flowers belongs
  in search_terms.

- Mood, composition, brightness, color, or aesthetic requests belong in
  visual_preferences.

- Explicit negatives such as "no portraits" belong in exclude_terms.

- If the user explicitly names an artwork medium, preserve it in medium.
  Examples include painting, oil painting, watercolor, drawing, etching,
  engraving, photograph, sculpture, and similar medium terms.

- The word "color" by itself is a visual preference, not a medium.

- If the user names an artist using a standard shorthand, surname, or commonly
  recognized artist name, normalize it to the canonical artist identity when
  the intended artist is clear from ordinary art usage.

- In particular, "Rembrandt" means "Rembrandt van Rijn", not artists whose
  names merely contain the word Rembrandt.

- Do not broaden an artist name to other artists with similar names.

- Leave artist, medium, culture_or_region, and dates null only when the user
  did not specify them.

- request_summary should briefly restate the actual user constraints without
  adding new ones.
"""

    response = client.responses.create(
        model=MODEL,
        reasoning={
            "effort": "none"
        },
        instructions=instructions,
        input=request_text,
        text={
            "format": {
                "type": (
                    "json_schema"
                ),
                "name": (
                    "art_request"
                ),
                "schema": schema,
                "strict": True,
            }
        },
    )

    result = json.loads(
        response.output_text
    )

    return normalize_interpretation(
        request_text,
        result,
    )


if __name__ == "__main__":
    from core.request_queue import (
        get_active_queue,
    )

    queue = get_active_queue()

    if not queue:
        raise SystemExit(
            "No queued requests."
        )

    request_item = queue[0]

    print("Request:")
    print(
        request_item[
            "request_text"
        ]
    )

    print()
    print(
        "Terra interpretation:"
    )

    print(
        json.dumps(
            interpret_request(
                request_item[
                    "request_text"
                ]
            ),
            indent=2,
        )
    )
