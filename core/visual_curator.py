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
    / "current"
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
            f"OpenAI environment file not found: {ENV_FILE}"
        )

    with ENV_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            key, separator, value = line.partition("=")

            if (
                separator
                and key == "OPENAI_API_KEY"
            ):
                os.environ[
                    "OPENAI_API_KEY"
                ] = value

                return

    raise RuntimeError(
        "OPENAI_API_KEY was not found."
    )


def load_manifest():
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
        return "No artwork has been displayed yet."

    recent = history[-20:]

    lines = []

    for entry in recent:
        lines.append(
            "- "
            f"{entry.get('title')} | "
            f"{entry.get('artist') or 'Unknown artist'} | "
            f"{entry.get('source')} | "
            f"{entry.get('medium') or 'Unknown medium'} | "
            f"{entry.get('orientation') or 'Unknown orientation'}"
        )

    return "\n".join(lines)


def build_candidate_text(candidate):
    return (
        f"Candidate {candidate['candidate_number']}\n"
        f"Source: {candidate['source']}\n"
        f"Title: {candidate['title']}\n"
        f"Artist: {candidate['artist'] or 'Unknown'}\n"
        f"Date: {candidate['date'] or 'Unknown'}\n"
        f"Medium: {candidate['medium'] or 'Unknown'}\n"
        f"Orientation: {candidate['orientation']}\n"
    )


def curate():
    load_api_key()

    manifest = load_manifest()

    if not manifest:
        raise RuntimeError(
            "The curation manifest is empty."
        )

    client = OpenAI()

    instructions = """
You are the visual curator for a single contemporary gallery-style
e-ink art frame.

The physical display is:
- 13.3-inch Spectra 6 e-ink
- 1600 x 1200 pixels
- landscape 4:3
- limited e-ink color palette
- matte, paper-like appearance
- artwork may need to be cropped to 4:3 later

Your job is to choose ONE artwork from today's candidate set.

Curatorial goals:
- The result should feel intentionally selected for a home gallery,
  not merely technically usable.
- Favor strong composition and visual presence.
- Consider how well the artwork is likely to survive reproduction
  on a limited-color Spectra 6 e-ink display.
- Consider whether a reasonable 4:3 presentation can be made without
  destroying the composition.
- Preserve variety and surprise.
- Do not automatically favor the most famous artist or canonical work.
- Paintings, drawings, prints, photographs, decorative arts, and
  culturally diverse works can all be excellent choices.
- Objects or artifacts may be selected when the image itself is
  visually compelling enough to work as wall art.
- Avoid choosing something merely because its metadata sounds
  prestigious.
- Use the ACTUAL IMAGE as the primary basis for visual judgment.
- Metadata is supporting context only.

The source adapters have already verified licensing, image quality,
and basic technical eligibility. Do not reconsider copyright.

Return a concise structured decision.
""".strip()

    content = [
        {
            "type": "input_text",
            "text": (
                instructions
                + "\n\nRECENT DISPLAY HISTORY:\n"
                + build_history_summary()
                + "\n\nTODAY'S CANDIDATES FOLLOW."
            ),
        }
    ]

    for candidate in manifest:
        content.append({
            "type": "input_text",
            "text": build_candidate_text(
                candidate
            ),
        })

        content.append({
            "type": "input_image",
            "image_url": image_to_data_url(
                candidate["thumbnail_path"]
            ),
            "detail": "high",
        })

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
                "name": "gallery_curation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "chosen_candidate_number": {
                            "type": "integer"
                        },
                        "reason": {
                            "type": "string"
                        },
                        "display_strengths": {
                            "type": "string"
                        },
                        "crop_assessment": {
                            "type": "string"
                        },
                        "eink_assessment": {
                            "type": "string"
                        },
                        "runner_up_candidate_number": {
                            "type": "integer"
                        }
                    },
                    "required": [
                        "chosen_candidate_number",
                        "reason",
                        "display_strengths",
                        "crop_assessment",
                        "eink_assessment",
                        "runner_up_candidate_number"
                    ],
                    "additionalProperties": False
                }
            }
        },
        max_output_tokens=500,
    )

    decision = json.loads(
        response.output_text
    )

    chosen_number = decision[
        "chosen_candidate_number"
    ]

    chosen = next(
        (
            candidate
            for candidate in manifest
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
    chosen, decision = curate()

    print("\nTERRA SELECTED\n")

    print(
        f"Candidate: "
        f"{chosen['candidate_number']}"
    )

    print(
        f"Title: {chosen['title']}"
    )

    print(
        f"Artist: "
        f"{chosen['artist'] or 'Unknown'}"
    )

    print(
        f"Source: {chosen['source']}"
    )

    print("\nCURATOR DECISION\n")

    print(
        json.dumps(
            decision,
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        "\nNo artwork has been added "
        "to display history."
    )


if __name__ == "__main__":
    main()
