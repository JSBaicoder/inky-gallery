import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path


GALLERY_DIR = Path.home() / "gallery"
LOG_DIR = GALLERY_DIR / "logs"


class Tee:
    def __init__(self, terminal, log_file):
        self.terminal = terminal
        self.log_file = log_file

    def write(self, text):
        self.terminal.write(text)
        self.log_file.write(text)

        self.terminal.flush()
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()


def get_log_path():
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    today = (
        datetime.now()
        .astimezone()
        .strftime("%Y-%m-%d")
    )

    return (
        LOG_DIR
        / f"gallery-{today}.log"
    )


def print_header():
    now = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    print()
    print("=" * 72)
    print("INKY GALLERY RUN")
    print(f"Started: {now}")
    print("=" * 72)
    print()


def print_footer(status):
    now = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    print()
    print("=" * 72)
    print(f"Run status: {status}")
    print(f"Finished: {now}")
    print("=" * 72)
    print()


def run():
    from core import preflight
    from core.daily_runner import run_daily
    from core.display_current import display_current
    from core.finalize_display import finalize_successful_display
    from core.cleanup import apply_cleanup, format_size

    print_header()

    print("Running preflight...")
    print()

    try:
        preflight.main()

    except SystemExit as error:
        code = error.code

        if code in (None, 0):
            code = 0

        if code != 0:
            print_footer(
                "FAILED - PREFLIGHT"
            )

            return int(code)

    print()
    print(
        "Preflight passed. "
        "Starting daily gallery pipeline..."
    )
    print()

    try:
        (
            manifest_path,
            selection,
            preparation,
            summary,
        ) = run_daily()

    except Exception:
        print()
        print(
            "DAILY GALLERY PIPELINE FAILED"
        )
        print()

        traceback.print_exc()

        print_footer(
            "FAILED - PIPELINE"
        )

        return 1

    print()
    print(
        "Artwork prepared successfully."
    )

    print()
    print(
        "Starting physical Inky refresh..."
    )
    print()

    try:
        display_current()

    except Exception:
        print()
        print(
            "INKY DISPLAY REFRESH FAILED"
        )
        print()

        traceback.print_exc()

        print()
        print(
            "Display history was NOT modified."
        )

        print_footer(
            "FAILED - DISPLAY"
        )

        return 1

    print()
    print(
        "Physical refresh completed."
    )

    print()
    print(
        "Recording successful display "
        "in history..."
    )

    try:
        history_entry = (
            finalize_successful_display()
        )

    except Exception:
        print()
        print(
            "DISPLAY SUCCEEDED BUT HISTORY "
            "RECORDING FAILED"
        )
        print()

        traceback.print_exc()

        print_footer(
            "FAILED - HISTORY"
        )

        return 1

    print()
    print(
        "Display history recorded."
    )

    print(
        f"Displayed: "
        f"{history_entry['title']}"
    )

    if history_entry.get("artist"):
        print(
            f"Artist: "
            f"{history_entry['artist']}"
        )

    print(
        f"Source: "
        f"{history_entry['source']}"
    )

    print()
    print(
        "Running old-image cleanup..."
    )

    try:
        cleanup_result = apply_cleanup(
            retention_days=7
        )

        print(
            f"Cleanup eligible: "
            f"{cleanup_result['eligible']}"
        )

        print(
            f"Cleanup deleted: "
            f"{cleanup_result['deleted']}"
        )

        print(
            "Cleanup recovered: "
            f"{format_size(cleanup_result['recovered_bytes'])}"
        )

        for error in cleanup_result["errors"]:
            print(
                f"[WARN] Cleanup error: {error}"
            )

    except Exception as error:
        print(
            f"[WARN] Cleanup failed: {error}"
        )

    print_footer(
        "SUCCESS - DISPLAYED"
    )

    return 0


def main():
    log_path = get_log_path()

    with log_path.open(
        "a",
        encoding="utf-8",
    ) as log_file:
        stdout_tee = Tee(
            sys.stdout,
            log_file,
        )

        stderr_tee = Tee(
            sys.stderr,
            log_file,
        )

        with redirect_stdout(stdout_tee):
            with redirect_stderr(stderr_tee):
                try:
                    exit_code = run()

                except Exception:
                    print()
                    print(
                        "UNEXPECTED RUNNER FAILURE"
                    )
                    print()

                    traceback.print_exc()

                    print_footer(
                        "FAILED - RUNNER"
                    )

                    exit_code = 1

                print(
                    f"Log file: {log_path}"
                )

    raise SystemExit(
        exit_code
    )


if __name__ == "__main__":
    main()
