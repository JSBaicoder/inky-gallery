import json
import subprocess

from datetime import date, timedelta
from pathlib import Path

from flask import (
    Flask,
    redirect,
    render_template_string,
    request,
    url_for,
)

from core.request_queue import (
    add_request,
    get_active_queue,
    load_queue,
)


GALLERY_DIR = Path.home() / "gallery"

SYSTEMCTL = "/bin/systemctl"
SUDO = "/usr/bin/sudo"
GALLERY_SERVICE = "inky-gallery.service"


app = Flask(__name__)


def get_current_artwork():
    selection_path = (
        GALLERY_DIR
        / "curation"
        / "current"
        / "selection.json"
    )

    if not selection_path.exists():
        return None

    try:
        with selection_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception:
        return None


def get_recent_request_history(
    limit=10,
):
    queue = load_queue()

    finished = [
        item
        for item in queue
        if item.get("status")
        != "queued"
    ]

    finished.sort(
        key=lambda item: (
            item.get("updated_at")
            or item.get("created_at")
            or ""
        ),
        reverse=True,
    )

    return finished[:limit]


def launch_gallery_update():
    result = subprocess.run(
        [
            SUDO,
            SYSTEMCTL,
            "start",
            "--no-block",
            GALLERY_SERVICE,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        error = (
            result.stderr.strip()
            or result.stdout.strip()
            or (
                "systemctl returned "
                f"code {result.returncode}"
            )
        )

        raise RuntimeError(error)


HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Inky Request Console</title>

  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 850px;
      margin: 40px auto;
      padding: 0 20px;
      line-height: 1.5;
    }

    h1, h2 {
      margin-bottom: 0.4rem;
    }

    .card {
      border: 1px solid #ccc;
      border-radius: 10px;
      padding: 18px;
      margin-bottom: 20px;
    }

    textarea,
    input[type="date"] {
      width: 100%;
      box-sizing: border-box;
      padding: 10px;
      font-size: 16px;
      margin-top: 8px;
      margin-bottom: 12px;
    }

    .buttons button {
      margin-right: 10px;
      margin-bottom: 10px;
      padding: 10px 14px;
      font-size: 15px;
      cursor: pointer;
    }

    .flash {
      background: #eef7ee;
      border: 1px solid #b8d8b8;
      padding: 10px 12px;
      border-radius: 8px;
      margin-bottom: 18px;
    }

    .small {
      color: #555;
      font-size: 14px;
    }

    .request-item {
      border-top: 1px solid #eee;
      padding: 12px 0;
    }

    .request-item:first-of-type {
      border-top: none;
    }

    .status {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: bold;
      margin-left: 6px;
    }

    .status-queued {
      background: #fff3cd;
      color: #705800;
    }

    .status-completed {
      background: #dff2e1;
      color: #245b2a;
    }

    .status-other {
      background: #eee;
      color: #444;
    }

    code {
      background: #f4f4f4;
      padding: 2px 5px;
      border-radius: 4px;
    }
  </style>
</head>

<body>
  <h1>Inky Request Console</h1>

  <p class="small">
    Local request page for your museum art frame.
  </p>

  {% if message %}
    <div class="flash">
      {{ message }}
    </div>
  {% endif %}

  <div class="card">
    <h2>Submit a request</h2>

    <form
      method="post"
      action="/submit"
    >
      <label for="request_text">
        What do you want to see?
      </label>

      <textarea
        id="request_text"
        name="request_text"
        rows="4"
        placeholder="Example: give me a colorful landscape from the 1800s"
      ></textarea>

      <label for="target_date">
        If using Specific Date:
      </label>

      <input
        type="date"
        id="target_date"
        name="target_date"
        value="{{ default_date }}"
      >

      <div class="buttons">
        <button
          type="submit"
          name="timing"
          value="now"
        >
          Update Now
        </button>

        <button
          type="submit"
          name="timing"
          value="tomorrow"
        >
          Tomorrow
        </button>

        <button
          type="submit"
          name="timing"
          value="date"
        >
          Specific Date
        </button>
      </div>
    </form>
  </div>

  <div class="card">
    <h2>Current artwork</h2>

    {% if current_artwork %}
      <p>
        <strong>Title:</strong>
        {{ current_artwork.get("title") }}
      </p>

      <p>
        <strong>Artist:</strong>
        {{ current_artwork.get("artist") or "Unknown artist" }}
      </p>

      <p>
        <strong>Source:</strong>
        {{ current_artwork.get("source") }}
      </p>
    {% else %}
      <p>
        No current artwork metadata found.
      </p>
    {% endif %}
  </div>

  <div class="card">
    <h2>Pending requests</h2>

    {% if active_queue %}
      {% for item in active_queue %}
        <div class="request-item">
          <strong>
            {{ item.request_text }}
          </strong>

          <span class="status status-queued">
            QUEUED
          </span>

          <br>

          <span class="small">
            {{ item.timing }}

            {% if item.target_date %}
              · {{ item.target_date }}
            {% endif %}
          </span>
        </div>
      {% endfor %}
    {% else %}
      <p>
        No pending requests.
      </p>
    {% endif %}
  </div>

  <div class="card">
    <h2>Recent requests</h2>

    {% if request_history %}
      {% for item in request_history %}
        <div class="request-item">
          <strong>
            {{ item.request_text }}
          </strong>

          {% if item.status == "completed" %}
            <span class="status status-completed">
              COMPLETED
            </span>
          {% else %}
            <span class="status status-other">
              {{ item.status | upper }}
            </span>
          {% endif %}

          <br>

          <span class="small">
            {{ item.timing }}

            {% if item.target_date %}
              · {{ item.target_date }}
            {% endif %}

            {% if item.updated_at %}
              · finished {{ item.updated_at }}
            {% endif %}
          </span>

          {% if item.interpreted_request %}
            {% if item.interpreted_request.request_summary %}
              <br>
              <span class="small">
                {{ item.interpreted_request.request_summary }}
              </span>
            {% endif %}
          {% endif %}
        </div>
      {% endfor %}
    {% else %}
      <p>
        No completed requests yet.
      </p>
    {% endif %}
  </div>
</body>
</html>
"""


@app.route(
    "/",
    methods=["GET"],
)
def index():
    active_queue = (
        get_active_queue()
    )

    request_history = (
        get_recent_request_history()
    )

    current_artwork = (
        get_current_artwork()
    )

    message = request.args.get(
        "message",
        "",
    )

    default_date = (
        date.today()
        + timedelta(days=1)
    ).isoformat()

    return render_template_string(
        HTML,
        active_queue=active_queue,
        request_history=(
            request_history
        ),
        current_artwork=(
            current_artwork
        ),
        message=message,
        default_date=default_date,
    )


@app.route(
    "/submit",
    methods=["POST"],
)
def submit():
    request_text = (
        request.form.get(
            "request_text"
        )
        or ""
    ).strip()

    timing = (
        request.form.get(
            "timing"
        )
        or ""
    ).strip()

    target_date = (
        request.form.get(
            "target_date"
        )
        or ""
    ).strip() or None

    if not request_text:
        return redirect(
            url_for(
                "index",
                message=(
                    "Request text is required."
                ),
            )
        )

    if timing not in {
        "now",
        "tomorrow",
        "date",
    }:
        return redirect(
            url_for(
                "index",
                message=(
                    "Invalid timing option."
                ),
            )
        )

    if (
        timing == "date"
        and not target_date
    ):
        return redirect(
            url_for(
                "index",
                message=(
                    "Specific Date requires "
                    "a date."
                ),
            )
        )

    if timing == "tomorrow":
        target_date = (
            date.today()
            + timedelta(days=1)
        ).isoformat()

    if timing == "now":
        target_date = (
            date.today()
            .isoformat()
        )

    entry = add_request(
        request_text=request_text,
        timing=timing,
        target_date=target_date,
    )

    if timing == "now":
        try:
            launch_gallery_update()

            message = (
                "Request queued and "
                "gallery update started: "
                f"{entry['request_text']}"
            )

        except Exception as error:
            message = (
                "Request was queued, but "
                "the immediate update could "
                "not be started: "
                f"{error}"
            )

    elif timing == "tomorrow":
        message = (
            "Request queued for tomorrow: "
            f"{entry['request_text']}"
        )

    else:
        message = (
            "Request queued for "
            f"{target_date}: "
            f"{entry['request_text']}"
        )

    return redirect(
        url_for(
            "index",
            message=message,
        )
    )


def main():
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=False,
    )


if __name__ == "__main__":
    main()
