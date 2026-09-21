import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


GALLERY_DIR = Path.home() / "gallery"

INPUT_DIR = GALLERY_DIR / "input"
OUTPUT_DIR = GALLERY_DIR / "output"

CURRENT_DIR = (
    GALLERY_DIR
    / "curation"
    / "current"
)

MANIFEST_FILE = (
    CURRENT_DIR
    / "manifest.json"
)

SELECTION_FILE = (
    CURRENT_DIR
    / "selection.json"
)

DEFAULT_RETENTION_DAYS = 7


def load_json(path):
    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return None


def get_protected_paths():
    protected = set()

    manifest = load_json(
        MANIFEST_FILE
    )

    if isinstance(manifest, list):
        for candidate in manifest:
            for key in (
                "original_image_path",
                "thumbnail_path",
            ):
                value = candidate.get(key)

                if value:
                    protected.add(
                        Path(value).resolve()
                    )

    selection = load_json(
        SELECTION_FILE
    )

    if isinstance(selection, dict):
        for key in (
            "original_image_path",
            "thumbnail_path",
        ):
            value = selection.get(key)

            if value:
                protected.add(
                    Path(value).resolve()
                )

    return protected


def find_cleanup_candidates(
    retention_days=DEFAULT_RETENTION_DAYS,
):
    cutoff = (
        datetime.now()
        - timedelta(
            days=retention_days
        )
    ).timestamp()

    protected = get_protected_paths()

    candidates = []

    for directory in (
        INPUT_DIR,
        OUTPUT_DIR,
    ):
        if not directory.exists():
            continue

        for path in directory.iterdir():
            if not path.is_file():
                continue

            if path.resolve() in protected:
                continue

            if path.stat().st_mtime >= cutoff:
                continue

            candidates.append(path)

    return sorted(
        candidates,
        key=lambda path: str(path),
    )


def format_size(byte_count):
    value = float(byte_count)

    for unit in (
        "B",
        "KB",
        "MB",
        "GB",
    ):
        if value < 1024:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} TB"


def apply_cleanup(
    retention_days=DEFAULT_RETENTION_DAYS,
):
    candidates = find_cleanup_candidates(
        retention_days
    )

    deleted = 0
    recovered = 0
    errors = []

    for path in candidates:
        try:
            size = path.stat().st_size

            path.unlink()

            deleted += 1
            recovered += size

        except FileNotFoundError:
            continue

        except OSError as error:
            errors.append(
                f"{path}: {error}"
            )

    return {
        "eligible": len(candidates),
        "deleted": deleted,
        "recovered_bytes": recovered,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Clean old gallery image files."
        )
    )

    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
    )

    args = parser.parse_args()

    if args.days < 1:
        raise SystemExit(
            "--days must be at least 1"
        )

    candidates = find_cleanup_candidates(
        args.days
    )

    total_bytes = sum(
        path.stat().st_size
        for path in candidates
        if path.exists()
    )

    print(
        "\nINKY GALLERY CLEANUP\n"
    )

    print(
        f"Retention window: "
        f"{args.days} day(s)"
    )

    print(
        f"Eligible files: "
        f"{len(candidates)}"
    )

    print(
        f"Potential space recovered: "
        f"{format_size(total_bytes)}"
    )

    if not candidates:
        print(
            "\nNothing needs cleanup."
        )
        return

    print("\nFILES")

    for path in candidates:
        print(f"  {path}")

    if not args.apply:
        print(
            "\nDRY RUN ONLY"
        )

        print(
            "No files were deleted."
        )

        return

    result = apply_cleanup(
        args.days
    )

    print(
        f"\nDeleted files: "
        f"{result['deleted']}"
    )

    print(
        "Space recovered: "
        f"{format_size(result['recovered_bytes'])}"
    )

    for error in result["errors"]:
        print(
            f"[WARN] {error}"
        )


if __name__ == "__main__":
    main()
