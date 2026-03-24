from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def appdata_root() -> Path:
    return Path(os.getenv("VIDEO2TIMELINE_APPDATA_ROOT", "/shared/app-data"))


def uploads_root() -> Path:
    return Path(os.getenv("VIDEO2TIMELINE_UPLOADS_ROOT", "/shared/uploads"))


def runtime_defaults_path() -> Path:
    return Path(os.getenv("VIDEO2TIMELINE_RUNTIME_DEFAULTS", "/app/config/runtime.defaults.json"))


def load_runtime_defaults() -> dict[str, Any]:
    path = runtime_defaults_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def settings_path() -> Path:
    return appdata_root() / "settings.json"


def token_path() -> Path:
    return appdata_root() / "secrets" / "huggingface.token"


def load_settings() -> dict[str, Any]:
    if settings_path().exists():
        return json.loads(settings_path().read_text(encoding="utf-8"))
    defaults = load_runtime_defaults()
    return {
        "schemaVersion": 1,
        "inputRoots": defaults.get("inputRoots", []),
        "outputRoots": defaults.get("outputRoots", []),
        "videoExtensions": defaults.get("videoExtensions", []),
        "huggingfaceTermsConfirmed": False,
    }


def load_huggingface_token() -> str | None:
    path = token_path()
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8", errors="replace").strip()
    return value or None
