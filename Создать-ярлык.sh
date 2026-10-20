#!/bin/sh
GAME_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$GAME_DIR/make_shortcut.py"
