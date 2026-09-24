import json
from datetime import date
from pathlib import Path

from core.request_candidate_pool import (
    build_request_candidate_pool,
)
from core.request_context import (
    attach_interpretation_if_missing,
    build_request_context,
    save_request_context,
)
from core.request_queue import (
    get_next_due_request,
)
from core.request_visual_curator import (
    curate_request,
)
from core.prepare_selected import (
    prepare_selected,
)


GALLERY_DIR = Path.home() / "gallery"

SELECTION_FILE = (
    GALLERY_DIR
    / "curation"
    / "current"
    / "selection.json"
)

DECISION_FILE = (
    GALLERY_DIR
    / "curation"
    / "request_pool"
    / "decision.json"
)


def save_request_selection(
    chosen,
    request_item,
    decision,
):
    selection = dict(chosen)

    selection[
        "selection_mode"
    ] = "requested_artwork"

    selection[
        "request_id"
    ] = request_item["id"]

    selection[
        "request_text"
    ] = request_item[
        "request_text"
    ]

    selection[
        "request_decision"
    ] = decision

    SELECTION_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SELECTION_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            selection,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return selection


def save_decision(
    request_item,
    decision,
    chosen,
):
    record = {
        "request_id": (
            request_item["id"]
        ),
        "request_text": (
            request_item[
                "request_text"
            ]
        ),
        "decision": decision,
        "selected_candidate": (
            chosen
        ),
    }

    DECISION_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DECISION_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            record,
            file,
            indent=2,
            ensure_ascii=False,
        )


def prepare_due_request(
    target_day=None,
):
    if target_day is None:
        target_day = (
            date.today().isoformat()
        )

    request_item = (
        get_next_due_request(
            target_day=target_day
        )
    )

    if not request_item:
        return {
            "status": "no_due_request",
            "request": None,
            "selection": None,
            "preparation": None,
            "decision": None,
        }

    print(
        "Due custom artwork request found:"
    )
    print(
        request_item[
            "request_text"
        ]
    )
    print()

    request_item = (
        attach_interpretation_if_missing(
            request_item
        )
    )

    context = build_request_context(
        request_item
    )

    save_request_context(
        context
    )

    print(
        "Request interpretation ready."
    )
    print(
        json.dumps(
            context,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    print(
        "Building four-museum "
        "candidate pool..."
    )

    manifest = (
        build_request_candidate_pool()
    )

    if not manifest.get(
        "candidates"
    ):
        return {
            "status": "no_candidates",
            "request": request_item,
            "selection": None,
            "preparation": None,
            "decision": None,
        }

    print()
    print(
        "Running single Terra "
        "visual comparison..."
    )
    print()

    chosen, decision = (
        curate_request()
    )

    save_decision(
        request_item,
        decision,
        chosen,
    )

    if chosen is None:
        print(
            "Terra found no acceptable "
            "match for the request."
        )

        return {
            "status": "no_match",
            "request": request_item,
            "selection": None,
            "preparation": None,
            "decision": decision,
        }

    selection = (
        save_request_selection(
            chosen,
            request_item,
            decision,
        )
    )

    print(
        "Terra selected:"
    )
    print(
        f"{selection['title']} "
        f"({selection['source']})"
    )
    print()

    preparation = (
        prepare_selected()
    )

    print()
    print(
        "Requested artwork prepared "
        "successfully."
    )
    print(
        "Display has NOT been changed."
    )
    print(
        "History has NOT been changed."
    )
    print(
        "Request has NOT been marked "
        "completed."
    )

    return {
        "status": "prepared",
        "request": request_item,
        "selection": selection,
        "preparation": preparation,
        "decision": decision,
    }


def main():
    result = prepare_due_request()

    print()
    print("REQUEST RUNNER RESULT")
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
