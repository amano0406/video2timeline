from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig, SourceDirectory


@dataclass
class VideoRecord:
    source_name: str
    path: str
    size_bytes: int


def _iter_files(source: SourceDirectory) -> list[Path]:
    root = Path(source.path)
    if not root.exists():
        return []
    iterator = root.rglob("*") if source.recursive else root.glob("*")
    return [path for path in iterator if path.is_file()]


def discover_videos(config: AppConfig) -> dict[str, object]:
    allowed = {ext.lower() for ext in config.video_extensions}
    rows: list[VideoRecord] = []
    missing_sources: list[str] = []

    for source in config.source_directories:
        root = Path(source.path)
        if not root.exists():
            missing_sources.append(source.path)
            continue
        for path in _iter_files(source):
            if path.suffix.lower() not in allowed:
                continue
            stat = path.stat()
            rows.append(
                VideoRecord(
                    source_name=source.name,
                    path=str(path),
                    size_bytes=stat.st_size,
                )
            )

    rows.sort(key=lambda row: row.path.lower())

    return {
        "project_name": config.project_name,
        "total_videos": len(rows),
        "missing_sources": missing_sources,
        "videos": [row.__dict__ for row in rows],
    }
