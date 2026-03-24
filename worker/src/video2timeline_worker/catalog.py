from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fs_utils import ensure_dir


def catalog_path(output_root: Path) -> Path:
    return output_root / ".video2timeline" / "catalog.jsonl"


def load_catalog(output_root: Path) -> dict[str, dict[str, Any]]:
    path = catalog_path(output_root)
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        file_hash = str(row.get("sha256") or "")
        if file_hash:
            rows[file_hash] = row
    return rows


def append_catalog_rows(output_root: Path, rows: list[dict[str, Any]]) -> None:
    path = catalog_path(output_root)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
