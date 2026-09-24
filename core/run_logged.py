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

    return LOG_DIR / f"gallery-{today}.log"


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


def run_autonomous(run_daily):
    print(
        "Starting normal autonomous "
        "gallery pipeline..."
    )
    print()

    run_daily()


def run():
    from core import preflight

    from core.cleanup import (
        apply_cleanup,
        format_size,
    )

    from core.daily_runner import run_daily

    from core.display_current import (
        display_current,
    )

    from core.finalize_display import (
        finalize_successful_display,
    )

    from core.request_queue import (
        mark_request_status,
    )

    from core.request_runner import (
        prepare_due_request,
    )

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
    print("Preflight passed.")
    print()

    # --------------------------------------------------
    # DETERMINE TODAY'S MODE
    # --------------------------------------------------

    run_mode = "autonomous"
    request_id = None

    print(
        "Checking for a due custom "
        "artwork request..."
    )
    print()

    try:
        request_result = (
            prepare_due_request()
        )

    except Exception:
        print(
            "CUSTOM REQUEST PREPARATION FAILED"
        )
        print()

        traceback.print_exc()

        print()
        print(
            "Falling back to the normal "
            "autonomous gallery."
        )
        print()

        request_result = {
            "status": "request_error",
            "request": None,
        }

    request_status = (
        request_result.get("status")
    )

    if request_status == "prepared":
        run_mode = "requested"

        request_item = (
            request_result.get("request")
            or {}
        )

        request_id = request_item.get(
            "id"
        )

        print()
        print(
            "Custom request prepared."
        )
        print(
            "It will take priority over "
            "autonomous curation today."
        )

    elif request_status == "no_due_request":
        print(
            "No custom request is due."
        )
        print()

        try:
            run_autonomous(
                run_daily
            )

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

    elif request_status in {
        "no_candidates",
        "no_match",
    }:
        request_item = (
            request_result.get("request")
            or {}
        )

        failed_request_id = (
            request_item.get("id")
        )

        print()
        print(
            "The custom request could not "
            "produce an acceptable artwork."
        )

        if failed_request_id:
            try:
                mark_request_status(
                    failed_request_id,
                    request_status,
                )

                print(
                    "Request status recorded "
                    f"as: {request_status}"
                )

            except Exception as error:
                print(
                    "[WARN] Could not update "
                    "request status: "
                    f"{error}"
                )

        print()
        print(
            "Falling back to the normal "
            "autonomous gallery."
        )
        print()

        try:
            run_autonomous(
                run_daily
            )

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

    else:
        if request_status != "request_error":
            print()
            print(
                "Unexpected request-runner "
                f"status: {request_status}"
            )
            print()

        try:
            run_autonomous(
                run_daily
            )

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

    # --------------------------------------------------
    # DISPLAY
    # --------------------------------------------------

    print()
    print(
        "Artwork prepared successfully."
    )
    print()

    if run_mode == "requested":
        print(
            "Display mode: CUSTOM REQUEST"
        )
    else:
        print(
            "Display mode: AUTONOMOUS"
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

        if run_mode == "requested":
            print(
                "Custom request was NOT "
                "marked completed."
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

    # --------------------------------------------------
    # HISTORY
    # --------------------------------------------------

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

        if run_mode == "requested":
            print()
            print(
                "Custom request was NOT "
                "marked completed."
            )

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

    # --------------------------------------------------
    # COMPLETE CUSTOM REQUEST
    # --------------------------------------------------

    if (
        run_mode == "requested"
        and request_id
    ):
        print()
        print(
            "Marking custom request "
            "completed..."
        )

        try:
            mark_request_status(
                request_id,
                "completed",
            )

            print(
                "Custom request marked "
                "completed."
            )

        except Exception:
            print()
            print(
                "DISPLAY AND HISTORY SUCCEEDED "
                "BUT REQUEST STATUS UPDATE FAILED"
            )
            print()

            traceback.print_exc()

            print_footer(
                "FAILED - REQUEST STATUS"
            )

            return 1

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------

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

        recovered_text = format_size(
            cleanup_result[
                "recovered_bytes"
            ]
        )

        print(
            f"Cleanup recovered: "
            f"{recovered_text}"
        )

        for error in cleanup_result["errors"]:
            print(
                f"[WARN] Cleanup error: "
                f"{error}"
            )

    except Exception as error:
        print(
            f"[WARN] Cleanup failed: "
            f"{error}"
        )

    if run_mode == "requested":
        print_footer(
            "SUCCESS - REQUEST DISPLAYED"
        )
    else:
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
                    f"Log file: "
                    f"{log_path}"
                )

    raise SystemExit(
        exit_code
    )


if __name__ == "__main__":
    main()
