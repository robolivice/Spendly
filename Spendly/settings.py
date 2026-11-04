from __future__ import annotations

import json
import os
import secrets
from typing import Any

import paths

DEFAULT_WINDOW = {"width": 1180, "height": 820, "x": None, "y": None}

_DEFAULTS: dict[str, Any] = {
    "version": 1,
    "secret_key": "",
    "window": dict(DEFAULT_WINDOW),
    "last_profile": None,
}

_cache: dict[str, Any] | None = None


def _read() -> dict[str, Any]:
    try:
        raw = paths.settings_path().read_text(encoding="utf-8")
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ValueError("settings root must be an object")
    except (OSError, ValueError):
        loaded = {}

    merged = json.loads(json.dumps(_DEFAULTS))
    for key, value in loaded.items():
        if key == "window" and isinstance(value, dict):
            merged["window"].update(value)
        else:
            merged[key] = value
    return merged


def load() -> dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = _read()
    return _cache


def save(values: dict[str, Any]) -> None:
    global _cache
    _cache = values
    target = paths.settings_path()
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, target)


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set(key: str, value: Any) -> None:
    values = dict(load())
    values[key] = value
    save(values)


def ensure_secret() -> str:
    current = load().get("secret_key")
    if isinstance(current, str) and current:
        return current
    key = secrets.token_hex(32)
    set("secret_key", key)
    return key


def window_state() -> dict[str, Any]:
    state = dict(DEFAULT_WINDOW)
    stored = get("window")
    if isinstance(stored, dict):
        state.update(stored)

    width = state.get("width")
    height = state.get("height")
    state["width"] = width if isinstance(width, int) and width >= 920 else DEFAULT_WINDOW["width"]
    state["height"] = height if isinstance(height, int) and height >= 620 else DEFAULT_WINDOW["height"]
    for axis in ("x", "y"):
        if not isinstance(state.get(axis), int):
            state[axis] = None
    return state
