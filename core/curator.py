import json
import random

from core.history import has_been_shown, load_history

from sources import cleveland
from sources import getty
from sources import met
from sources import nga


SOURCES = {
    "met": met.find_artwork,
    "cleveland": cleveland.find_artwork,
    "getty": getty.find_artwork,
    "nga": nga.find_artwork,
}

ATTEMPTS_PER_SOURCE = 3


LOW_DISPLAY_VALUE_TITLE_PHRASES = (
    "left foot",
    "right foot",
    "mount from",
    "handle from",
    "fragment of a handle",
    "fragment of handle",
    "sherd",
    "shard",
)


def normalize(value):
    if not value:
        return ""

    return " ".join(
        value.lower().split()
    )


def get_recent_history(history, count=20):
    return history[-count:]


def recent_artist_seen(
    artwork,
    history,
    lookback=20,
):
    artist = normalize(artwork.artist)

    if not artist:
        return False

    for entry in get_recent_history(
        history,
        lookback,
    ):
        previous_artist = normalize(
            entry.get("artist")
        )

        if previous_artist == artist:
            return True

    return False


def has_low_display_value_title(artwork):
    title = normalize(artwork.title)

    return any(
        phrase in title
        for phrase
        in LOW_DISPLAY_VALUE_TITLE_PHRASES
    )


def orientation_streak(history):
    if not history:
        return None, 0

    last_orientation = history[-1].get(
        "orientation"
    )

    if not last_orientation:
        return None, 0

    streak = 0

    for entry in reversed(history):
        if (
            entry.get("orientation")
            != last_orientation
        ):
            break

        streak += 1

    return last_orientation, streak


def score_artwork(
    artwork,
    history,
):
    reasons = []

    if has_been_shown(artwork):
        return 0, [
            "already shown"
        ]

    if has_low_display_value_title(
        artwork
    ):
        return 0, [
            "likely isolated object component"
        ]

    score = 100

    if recent_artist_seen(
        artwork,
        history,
    ):
        score -= 45
        reasons.append(
            "artist appeared recently"
        )

    last_orientation, streak = (
        orientation_streak(history)
    )

    if (
        streak >= 3
        and artwork.orientation
        == last_orientation
    ):
        score -= 20
        reasons.append(
            "orientation appeared repeatedly"
        )

    recent = get_recent_history(
        history,
        5,
    )

    medium = normalize(
        artwork.medium
    )

    if medium:
        recent_media = [
            normalize(
                entry.get("medium")
            )
            for entry in recent
        ]

        if medium in recent_media:
            score -= 15
            reasons.append(
                "same medium appeared recently"
            )

    if not artwork.artist:
        score -= 5
        reasons.append(
            "artist unknown"
        )

    if not artwork.date:
        score -= 3
        reasons.append(
            "date unavailable"
        )

    if not reasons:
        reasons.append(
            "no metadata concerns"
        )

    return max(score, 0), reasons


def get_candidate_from_source(
    source_name,
    history,
):
    finder = SOURCES[source_name]

    rejected = []

    for attempt in range(
        1,
        ATTEMPTS_PER_SOURCE + 1,
    ):
        try:
            artwork, image_path = finder()

        except Exception as error:
            rejected.append({
                "attempt": attempt,
                "reason": (
                    f"source error: {error}"
                ),
            })

            continue

        if not artwork:
            rejected.append({
                "attempt": attempt,
                "reason": (
                    "no eligible artwork returned"
                ),
            })

            continue

        score, reasons = score_artwork(
            artwork,
            history,
        )

        if score <= 0:
            rejected.append({
                "attempt": attempt,
                "source_id": artwork.source_id,
                "title": artwork.title,
                "score": score,
                "reason": "; ".join(
                    reasons
                ),
            })

            continue

        return {
            "artwork": artwork,
            "image_path": image_path,
            "metadata_score": score,
            "metadata_notes": reasons,
            "rejected": rejected,
        }

    return None


def build_shortlist():
    history = load_history()

    source_names = list(
        SOURCES.keys()
    )

    random.shuffle(
        source_names
    )

    candidates = []

    for source_name in source_names:
        result = get_candidate_from_source(
            source_name,
            history,
        )

        if not result:
            continue

        artwork = result["artwork"]

        candidates.append({
            "source": artwork.source,
            "source_id": artwork.source_id,
            "title": artwork.title,
            "artist": artwork.artist,
            "date": artwork.date,
            "medium": artwork.medium,
            "orientation": artwork.orientation,
            "image_path": str(
                result["image_path"]
            ),
            "source_url": artwork.source_url,
            "metadata_score": (
                result["metadata_score"]
            ),
            "metadata_notes": (
                result["metadata_notes"]
            ),
        })

    return candidates


def main():
    candidates = build_shortlist()

    if not candidates:
        print(
            "No curator candidates found."
        )
        return

    print(
        f"CANDIDATES: {len(candidates)}"
    )

    print(
        json.dumps(
            candidates,
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        "\nNo artwork has been selected "
        "or added to display history yet."
    )


if __name__ == "__main__":
    main()
