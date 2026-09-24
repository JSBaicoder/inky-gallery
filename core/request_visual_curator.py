import base64
import json
import os
from pathlib import Path

from openai import OpenAI

from core.history import load_history


GALLERY_DIR = Path.home() / "gallery"

MANIFEST_FILE = (
    GALLERY_DIR
    / "curation"
    / "request_pool"
    / "manifest.json"
)

ENV_FILE = (
    Path.home()
    / ".config"
    / "inky"
    / "openai.env"
)

MODEL = "gpt-5.6-terra"


def load_api_key():
    if os.getenv("OPENAI_API_KEY"):
        return

    if not ENV_FILE.exists():
        raise RuntimeError(
            f"OpenAI environment file not found: "
            f"{ENV_FILE}"
        )

    with ENV_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if (
                not line
                or line.startswith("#")
            ):
                continue

            key, separator, value = (
                line.partition("=")
            )

            if (
                separator
                and key
                == "OPENAI_API_KEY"
            ):
                os.environ[
                    "OPENAI_API_KEY"
                ] = value

                return

    raise RuntimeError(
        "OPENAI_API_KEY was not found."
    )


def load_manifest():
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(
            f"Request manifest not found: "
            f"{MANIFEST_FILE}"
        )

    with MANIFEST_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def image_to_data_url(path):
    path = Path(path)

    encoded = base64.b64encode(
        path.read_bytes()
    ).decode("ascii")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


def build_history_summary():
    history = load_history()

    if not history:
        return (
            "No artwork has been "
            "displayed yet."
        )

    recent = history[-20:]

    lines = []

    for entry in recent:
        lines.append(
            "- "
            f"{entry.get('title')} | "
            f"{entry.get('artist') or 'Unknown artist'} | "
            f"{entry.get('source')} | "
            f"{entry.get('medium') or 'Unknown medium'}"
        )

    return "\n".join(lines)


def build_candidate_text(
    candidate,
):
    return (
        f"Candidate "
        f"{candidate['candidate_number']}\n"
        f"Source: "
        f"{candidate['source']}\n"
        f"Title: "
        f"{candidate['title']}\n"
        f"Artist: "
        f"{candidate['artist'] or 'Unknown'}\n"
        f"Date: "
        f"{candidate['date'] or 'Unknown'}\n"
        f"Medium: "
        f"{candidate['medium'] or 'Unknown'}\n"
        f"Orientation: "
        f"{candidate['orientation']}\n"
    )


def curate_request():
    load_api_key()

    manifest = load_manifest()

    request_context = (
        manifest.get(
            "request_context"
        )
        or {}
    )

    candidates = (
        manifest.get("candidates")
        or []
    )

    if not candidates:
        raise RuntimeError(
            "Request candidate pool "
            "is empty."
        )

    request_text = (
        request_context.get(
            "request_text"
        )
        or ""
    )

    request_summary = (
        request_context.get(
            "request_summary"
        )
        or request_text
    )

    client = OpenAI()

    instructions = """
You are the final visual curator for a
contemporary gallery-style e-ink art frame.

You are reviewing a small candidate pool
created specifically in response to a user's
artwork request.

The physical display is:

- 13.3-inch Spectra 6 e-ink
- 1600 x 1200 pixels
- landscape 4:3
- limited e-ink color palette
- matte, paper-like appearance

Your FIRST responsibility is to satisfy the
user's actual request.

Use the ACTUAL IMAGES as the primary evidence
for visible-subject and aesthetic requirements.
Metadata may be used for factual requirements
such as date, artist, medium, or culture.

Important rules:

- Do not approve a work merely because metadata
  happens to contain the requested keyword.
- A requested visible subject should be clearly
  and meaningfully present.
- Incidental tiny details do not satisfy a
  subject request.
- Respect explicit exclusions.
- Respect requested date ranges, artists,
  media, cultures, and regions.
- Do not silently relax the user's request.
- If none of the candidates reasonably fulfills
  the request, return status "no_match".
- Do not choose a bad candidate merely because
  you must choose something.

Among candidates that genuinely satisfy the
request, choose the one that will work best as
wall art on the e-ink frame.

For that final choice consider:

- visual presence
- composition
- how well the work survives the limited
  Spectra 6 palette
- suitability for a 4:3 presentation
- diversity from recently displayed art
- overall gallery quality

Do not automatically favor a famous artist.

Return a concise structured decision.
""".strip()

    content = [
        {
            "type": "input_text",
            "text": (
                instructions
                + "\n\nUSER REQUEST:\n"
                + request_text
                + "\n\nSTRUCTURED REQUEST:\n"
                + json.dumps(
                    request_context,
                    ensure_ascii=False,
                )
                + "\n\nREQUEST SUMMARY:\n"
                + request_summary
                + "\n\nRECENT DISPLAY HISTORY:\n"
                + build_history_summary()
                + "\n\nCANDIDATES FOLLOW."
            ),
        }
    ]

    for candidate in candidates:
        content.append(
            {
                "type": "input_text",
                "text": (
                    build_candidate_text(
                        candidate
                    )
                ),
            }
        )

        content.append(
            {
                "type": "input_image",
                "image_url": (
                    image_to_data_url(
                        candidate[
                            "thumbnail_path"
                        ]
                    )
                ),
                "detail": "high",
            }
        )

    response = client.responses.create(
        model=MODEL,
        reasoning={
            "effort": "none"
        },
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": (
                    "request_gallery_curation"
                ),
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": [
                                "match",
                                "no_match",
                            ],
                        },
                        "chosen_candidate_number": {
                            "type": [
                                "integer",
                                "null",
                            ]
                        },
                        "runner_up_candidate_number": {
                            "type": [
                                "integer",
                                "null",
                            ]
                        },
                        "request_match_reason": {
                            "type": "string"
                        },
                        "display_reason": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "status",
                        "chosen_candidate_number",
                        "runner_up_candidate_number",
                        "request_match_reason",
                        "display_reason",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        max_output_tokens=400,
    )

    decision = json.loads(
        response.output_text
    )

    if decision["status"] == "no_match":
        return None, decision

    chosen_number = decision[
        "chosen_candidate_number"
    ]

    chosen = next(
        (
            candidate
            for candidate
            in candidates
            if candidate[
                "candidate_number"
            ] == chosen_number
        ),
        None,
    )

    if chosen is None:
        raise RuntimeError(
            "Terra returned an invalid "
            "candidate number."
        )

    return chosen, decision


def main():
    chosen, decision = (
        curate_request()
    )

    print()
    print("TERRA REQUEST DECISION")
    print()

    print(
        json.dumps(
            decision,
            indent=2,
            ensure_ascii=False,
        )
    )

    if chosen is None:
        print()
        print(
            "No candidate was approved "
            "for this request."
        )
        return

    print()
    print("SELECTED ARTWORK")
    print()

    print(
        f"Candidate: "
        f"{chosen['candidate_number']}"
    )
    print(
        f"Title: "
        f"{chosen['title']}"
    )
    print(
        f"Artist: "
        f"{chosen['artist'] or 'Unknown'}"
    )
    print(
        f"Source: "
        f"{chosen['source']}"
    )

    print()
    print(
        "No display or history change "
        "has been made."
    )


if __name__ == "__main__":
    main()
