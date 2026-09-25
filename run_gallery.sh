#!/bin/bash

set -u

GALLERY_DIR="$HOME/gallery"
VENV_DIR="$HOME/inky-venv"
LOCK_DIR="$GALLERY_DIR/.run_lock"

cleanup() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Gallery run already in progress. Exiting."
    exit 1
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "ERROR: Python virtual environment not found:"
    echo "$VENV_DIR"
    exit 1
fi

cd "$GALLERY_DIR" || exit 1

source "$VENV_DIR/bin/activate"

python -m core.run_logged
