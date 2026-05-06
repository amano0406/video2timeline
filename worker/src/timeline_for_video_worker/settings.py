from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PRODUCT_NAME = "TimelineForVideo"
SCHEMA_VERSION = 1

SETTINGS_PATH_ENV = "TIMELINE_FOR_VIDEO_SETTINGS_PATH"
SETTINGS_EXAMPLE_PATH_ENV = "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH"

DEFAULT_SETTINGS: dict[str, Any] = {
    "schemaVersion": SCHEMA_VERSION,
    "inputRoots": ["C:\\TimelineData\\input-video\\"],
    "outputRoot": "C:\\TimelineData\\video",
}


class SettingsError(ValueError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def settings_path() -> Path:
    configured = os.environ.get(SETTINGS_PATH_ENV)
    if configured:
        return Path(configured)
    return repo_root() / "settings.json"


def settings_example_path() -> Path:
    configured = os.environ.get(SETTINGS_EXAMPLE_PATH_ENV)
    if configured:
        return Path(configured)
    return repo_root() / "settings.example.json"


def default_settings() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"Settings file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SettingsError(f"Settings file is not valid JSON: {path}") from exc

    if not isinstance(raw, dict):
        raise SettingsError(f"Settings file must contain a JSON object: {path}")
    return raw


def load_example_settings() -> dict[str, Any]:
    path = settings_example_path()
    if path.exists():
        return normalize_settings(read_json(path))
    return default_settings()


def load_settings(path: Path | None = None) -> dict[str, Any]:
    return normalize_settings(read_json(path or settings_path()))


def normalize_settings(raw: dict[str, Any]) -> dict[str, Any]:
    schema_version = raw.get("schemaVersion")
    if schema_version != SCHEMA_VERSION:
        raise SettingsError(f"Unsupported schemaVersion: {schema_version!r}")

    input_roots_raw = raw.get("inputRoots")
    if not isinstance(input_roots_raw, list):
        raise SettingsError("inputRoots must be a list of path strings.")

    input_roots: list[str] = []
    seen: set[str] = set()
    for value in input_roots_raw:
        if not isinstance(value, str):
            raise SettingsError("inputRoots must contain only path strings.")
        normalized = value.strip()
        if not normalized:
            raise SettingsError("inputRoots cannot contain empty paths.")
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            input_roots.append(normalized)

    output_root_raw = raw.get("outputRoot")
    if not isinstance(output_root_raw, str) or not output_root_raw.strip():
        raise SettingsError("outputRoot must be a non-empty path string.")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "inputRoots": input_roots,
        "outputRoot": output_root_raw.strip(),
    }


def save_settings(settings: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    normalized = normalize_settings(settings)
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
