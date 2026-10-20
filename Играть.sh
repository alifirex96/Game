#!/bin/sh
# No installation, elevated permissions or packages are used.
GAME_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --text='В системе не найден Python 3.7 или новее. Эта сборка использует системный Python.'
    else
        printf '%s\n' 'Не найден Python 3.7 или новее. Запуск этой сборки невозможен.'
    fi
    exit 1
fi
exec python3 "$GAME_DIR/launcher.py"
