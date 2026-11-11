from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Spendly"
APP_VERSION = "1.3.2"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION}"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def exe_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def is_portable() -> bool:
    return (exe_dir() / "portable.txt").is_file()


def data_dir() -> Path:
    override = os.environ.get("SPENDLY_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    elif is_portable():
        path = exe_dir() / "data"
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        path = Path(base) / APP_NAME if base else Path.home() / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME")
        path = (Path(base) if base else Path.home() / ".local" / "share") / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent
    return root.joinpath(*parts)


def db_path() -> Path:
    return data_dir() / "spendly.db"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def backup_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def webview_dir() -> Path:
    path = data_dir() / "webview"
    path.mkdir(parents=True, exist_ok=True)
    return path
