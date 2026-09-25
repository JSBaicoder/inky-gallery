import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


GALLERY_DIR = Path.home() / "gallery"
ENV_FILE = Path.home() / ".config" / "inky" / "openai.env"

MODEL = "gpt-5.6-terra"

EXPECTED_INKY_RESOLUTION = (1600, 1200)

WITTY_SERVICE = "wp5d.service"
WITTY_I2C_BUS = 1
WITTY_I2C_ADDRESS = 0x51

MIN_CRITICAL_FREE_BYTES = 500 * 1024 * 1024
MIN_RECOMMENDED_FREE_BYTES = 2 * 1024 * 1024 * 1024


REQUIRED_FILES = [
    GALLERY_DIR / "core" / "artwork.py",
    GALLERY_DIR / "core" / "curator.py",
    GALLERY_DIR / "core" / "daily_runner.py",
    GALLERY_DIR / "core" / "history.py",
    GALLERY_DIR / "core" / "visual_curator.py",
    GALLERY_DIR / "core" / "prepare_selected.py",
    GALLERY_DIR / "core" / "finalize_display.py",
    GALLERY_DIR / "core" / "display_current.py",
    GALLERY_DIR / "sources" / "met.py",
    GALLERY_DIR / "sources" / "cleveland.py",
    GALLERY_DIR / "sources" / "getty.py",
    GALLERY_DIR / "sources" / "nga.py",
]


REQUIRED_DIRECTORIES = [
    GALLERY_DIR / "input",
    GALLERY_DIR / "output",
    GALLERY_DIR / "data",
    GALLERY_DIR / "curation",
    GALLERY_DIR / "logs",
]


SOURCE_CHECKS = {
    "Met": (
        "https://collectionapi.metmuseum.org/"
        "public/collection/v1.1/search"
        "?q=painting&hasImages=true&limit=1"
    ),
    "Cleveland": (
        "https://openaccess-api.clevelandart.org/"
        "api/artworks/"
        "?cc0=true&has_image=1&limit=1"
    ),
    "Getty": (
        "https://data.getty.edu/museum/collection/"
    ),
    "NGA": (
        "https://raw.githubusercontent.com/"
        "NationalGalleryOfArt/opendata/"
        "main/data/published_images.csv"
    ),
}


def pass_result(message):
    print(f"[PASS] {message}")


def warn_result(message):
    print(f"[WARN] {message}")


def fail_result(message):
    print(f"[FAIL] {message}")


def format_bytes(value):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024


def load_api_key():
    existing = os.getenv("OPENAI_API_KEY")

    if existing:
        return existing

    if not ENV_FILE.exists():
        return None

    with ENV_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            key, separator, value = line.partition("=")

            if (
                separator
                and key == "OPENAI_API_KEY"
                and value
            ):
                os.environ["OPENAI_API_KEY"] = value
                return value

    return None


def check_required_files():
    failures = 0

    missing = [
        path
        for path in REQUIRED_FILES
        if not path.exists()
    ]

    if missing:
        for path in missing:
            fail_result(
                f"Missing required file: {path}"
            )
        failures += len(missing)
    else:
        pass_result(
            "All required gallery source files exist."
        )

    return failures


def check_directories():
    failures = 0

    for directory in REQUIRED_DIRECTORIES:
        if not directory.exists():
            fail_result(
                f"Missing directory: {directory}"
            )
            failures += 1
            continue

        if not directory.is_dir():
            fail_result(
                "Expected directory but found "
                f"something else: {directory}"
            )
            failures += 1

    if failures == 0:
        pass_result(
            "Required gallery directories exist."
        )

    return failures


def check_write_access():
    try:
        with tempfile.NamedTemporaryFile(
            dir=GALLERY_DIR,
            prefix=".preflight_",
            delete=True,
        ) as temp_file:
            temp_file.write(b"ok")
            temp_file.flush()

        pass_result(
            "Gallery directory is writable."
        )
        return 0

    except Exception as error:
        fail_result(
            "Gallery directory is not writable: "
            f"{error}"
        )
        return 1


def check_disk_space():
    usage = shutil.disk_usage(GALLERY_DIR)
    free = usage.free

    if free < MIN_CRITICAL_FREE_BYTES:
        fail_result(
            "Critically low disk space: "
            f"{format_bytes(free)} free."
        )
        return 1

    if free < MIN_RECOMMENDED_FREE_BYTES:
        warn_result(
            "Disk space is getting low: "
            f"{format_bytes(free)} free."
        )
        return 0

    pass_result(
        f"Disk space: {format_bytes(free)} free."
    )
    return 0


def check_python_dependencies():
    failures = 0

    try:
        import PIL  # noqa: F401

        pass_result(
            "Pillow is installed."
        )
    except ImportError:
        fail_result(
            "Pillow is not installed."
        )
        failures += 1

    try:
        import openai  # noqa: F401

        pass_result(
            "OpenAI Python SDK is installed."
        )
    except ImportError:
        fail_result(
            "OpenAI Python SDK is not installed."
        )
        failures += 1

    try:
        import inky  # noqa: F401

        pass_result(
            "Inky Python library is installed."
        )
    except ImportError:
        fail_result(
            "Inky Python library is not installed."
        )
        failures += 1

    return failures


def check_api_key_file():
    if not ENV_FILE.exists():
        fail_result(
            "OpenAI environment file is missing: "
            f"{ENV_FILE}"
        )
        return 1

    mode = stat.S_IMODE(
        ENV_FILE.stat().st_mode
    )

    if mode != 0o600:
        warn_result(
            "OpenAI environment file permissions "
            f"are {oct(mode)}; expected 0o600."
        )
    else:
        pass_result(
            "OpenAI environment file permissions "
            "are secure."
        )

    api_key = load_api_key()

    if not api_key:
        fail_result(
            "OPENAI_API_KEY could not be loaded."
        )
        return 1

    pass_result(
        "OPENAI_API_KEY is available."
    )
    return 0


def check_openai():
    try:
        from openai import OpenAI

        client = OpenAI()

        model = client.models.retrieve(
            MODEL
        )

        if model.id != MODEL:
            fail_result(
                "Unexpected OpenAI model response: "
                f"{model.id}"
            )
            return 1

        pass_result(
            "OpenAI connection works and "
            f"{MODEL} is available."
        )
        return 0

    except Exception as error:
        fail_result(
            f"OpenAI API check failed: {error}"
        )
        return 1


def check_url(name, url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; Gallery/1.0)"
            ),
            "Range": "bytes=0-1023",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=20,
        ) as response:
            response.read(1024)

        pass_result(
            f"{name} source is reachable."
        )
        return True

    except Exception as error:
        warn_result(
            f"{name} source check failed: {error}"
        )
        return False


def check_sources():
    available = 0

    for name, url in SOURCE_CHECKS.items():
        if check_url(name, url):
            available += 1

    if available == 0:
        fail_result(
            "None of the museum sources "
            "are reachable."
        )
        return 1

    if available < len(SOURCE_CHECKS):
        warn_result(
            f"{available}/{len(SOURCE_CHECKS)} "
            "museum sources are currently reachable."
        )
    else:
        pass_result(
            "All four museum sources are reachable."
        )

    return 0


def check_inky():
    try:
        from inky.auto import auto

        display = auto()
        resolution = display.resolution

        if resolution != EXPECTED_INKY_RESOLUTION:
            fail_result(
                "Unexpected Inky resolution: "
                f"{resolution}"
            )
            return 1

        pass_result(
            "Inky display detected at 1600x1200."
        )
        return 0

    except Exception as error:
        fail_result(
            f"Inky detection failed: {error}"
        )
        return 1


def check_witty():
    failures = 0

    try:
        service = subprocess.run(
            [
                "systemctl",
                "is-active",
                "--quiet",
                WITTY_SERVICE,
            ],
            check=False,
        )

        if service.returncode == 0:
            pass_result(
                "Witty Pi 5 daemon is active."
            )
        else:
            fail_result(
                "Witty Pi 5 daemon is not active."
            )
            failures += 1

    except Exception as error:
        fail_result(
            "Could not check Witty Pi 5 daemon: "
            f"{error}"
        )
        failures += 1

    try:
        result = subprocess.run(
            [
                "i2cdetect",
                "-y",
                str(WITTY_I2C_BUS),
                hex(WITTY_I2C_ADDRESS),
                hex(WITTY_I2C_ADDRESS),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            fail_result(
                "Witty Pi 5 I2C probe failed."
            )
            failures += 1
        else:
            witty_found = bool(
                re.search(
                    r"^50:.*\b51\b",
                    result.stdout,
                    re.MULTILINE,
                )
            )

            if witty_found:
                pass_result(
                    "Witty Pi 5 detected at I2C address 0x51."
                )
            else:
                fail_result(
                    "Witty Pi 5 not detected at "
                    "I2C address 0x51."
                )
                failures += 1

    except FileNotFoundError:
        fail_result(
            "i2cdetect is not installed."
        )
        failures += 1

    except Exception as error:
        fail_result(
            "Witty Pi 5 I2C check failed: "
            f"{error}"
        )
        failures += 1

    return failures


def main():
    print(
        "\nINKY GALLERY PREFLIGHT\n"
    )

    failures = 0

    failures += check_required_files()
    failures += check_directories()
    failures += check_write_access()
    failures += check_disk_space()
    failures += check_python_dependencies()
    failures += check_api_key_file()

    if os.getenv("OPENAI_API_KEY"):
        failures += check_openai()

    failures += check_sources()

    print(
        "\nHARDWARE CHECKS"
    )

    failures += check_inky()
    failures += check_witty()

    if failures:
        print(
            "\nPREFLIGHT FAILED: "
            f"{failures} critical problem(s)."
        )
        sys.exit(1)

    print(
        "\nPREFLIGHT PASSED"
    )

    print(
        "The gallery system is ready."
    )


if __name__ == "__main__":
    main()
