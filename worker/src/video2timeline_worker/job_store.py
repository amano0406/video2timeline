from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .contracts import InputItem, JobRequest, JobResult, JobStatus
from .discovery import discover_videos
from .fs_utils import ensure_dir, now_iso, write_text
from .settings import load_huggingface_token, load_settings


def _allowed_extensions(settings: dict[str, Any]) -> set[str]:
    return {
        ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
        for ext in settings.get("videoExtensions", [])
        if str(ext).strip()
    }


def _enabled_output_root(
    settings: dict[str, Any], output_root_id: str | None = None
) -> dict[str, Any]:
    enabled = [
        root
        for root in settings.get("outputRoots", [])
        if root.get("enabled", True) and root.get("path")
    ]
    if output_root_id:
        for root in enabled:
            if str(root.get("id") or "").lower() == output_root_id.lower():
                return root
        raise ValueError(f"Output root not found or disabled: {output_root_id}")
    if not enabled:
        raise ValueError("No enabled output root is configured.")
    return enabled[0]


def _enabled_input_roots(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        root
        for root in settings.get("inputRoots", [])
        if root.get("enabled", True) and root.get("path")
    ]


def _iter_videos(directory: Path, allowed_extensions: set[str]) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        [
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in allowed_extensions
        ],
        key=lambda item: str(item).lower(),
    )


def collect_input_items(
    *,
    settings: dict[str, Any],
    files: list[Path] | None = None,
    directories: list[Path] | None = None,
    source_ids: list[str] | None = None,
) -> list[InputItem]:
    allowed_extensions = _allowed_extensions(settings)
    rows: list[InputItem] = []
    seen_paths: set[str] = set()

    def add_path(path: Path, source_kind: str, source_id: str) -> None:
        resolved = path.resolve()
        key = str(resolved).lower()
        if key in seen_paths:
            return
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Input file was not found: {resolved}")
        if resolved.suffix.lower() not in allowed_extensions:
            return
        seen_paths.add(key)
        size_bytes = resolved.stat().st_size
        rows.append(
            InputItem(
                input_id=f"{source_kind[:4]}-{len(rows) + 1:04d}",
                source_kind=source_kind,
                source_id=source_id,
                original_path=str(resolved),
                display_name=resolved.name,
                size_bytes=size_bytes,
            )
        )

    for file_path in files or []:
        add_path(file_path, "local_file", "local")

    for directory in directories or []:
        resolved_directory = directory.resolve()
        if not resolved_directory.exists() or not resolved_directory.is_dir():
            raise ValueError(f"Input directory was not found: {resolved_directory}")
        for file_path in _iter_videos(resolved_directory, allowed_extensions):
            add_path(file_path, "local_directory", str(resolved_directory))

    if source_ids:
        from .cli import _runtime_config  # local import to avoid circular top-level import

        selected_ids = {value.lower() for value in source_ids}
        config = _runtime_config()
        discovered = discover_videos(config)
        for row in discovered.get("videos", []):
            source_name = str(row.get("source_name") or "")
            source_root = next(
                (
                    root
                    for root in _enabled_input_roots(settings)
                    if str(root.get("id") or "").lower() == source_name.lower()
                ),
                None,
            )
            if source_root is None:
                continue
            if source_name.lower() not in selected_ids:
                continue
            add_path(
                Path(str(row["path"])), "mounted_root", str(source_root.get("id") or source_name)
            )

    return rows


def list_runs(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    settings = settings or load_settings()
    rows: list[dict[str, Any]] = []
    for root in _enabled_output_root_list(settings):
        output_path = Path(str(root["path"]))
        if not output_path.exists():
            continue
        for run_dir in sorted(output_path.glob("run-*"), key=lambda item: item.name, reverse=True):
            request_path = run_dir / "request.json"
            status_path = run_dir / "status.json"
            manifest_path = run_dir / "manifest.json"
            if not request_path.exists() or not status_path.exists():
                continue
            request = json.loads(request_path.read_text(encoding="utf-8-sig", errors="replace"))
            status = json.loads(status_path.read_text(encoding="utf-8-sig", errors="replace"))
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8-sig", errors="replace"))
                if manifest_path.exists()
                else {"items": []}
            )
            items = manifest.get("items", [])
            rows.append(
                {
                    "job_id": request.get("job_id", run_dir.name),
                    "run_dir": str(run_dir),
                    "state": status.get("state", "unknown"),
                    "current_stage": status.get("current_stage", ""),
                    "videos_total": status.get("videos_total", 0),
                    "videos_done": status.get("videos_done", 0),
                    "videos_skipped": status.get("videos_skipped", 0),
                    "videos_failed": status.get("videos_failed", 0),
                    "updated_at": status.get("updated_at"),
                    "created_at": request.get("created_at"),
                    "total_size_bytes": sum(int(item.get("size_bytes", 0)) for item in items),
                    "total_duration_sec": sum(
                        float(item.get("duration_seconds", 0.0)) for item in items
                    ),
                }
            )
    return rows


def _enabled_output_root_list(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        root
        for root in settings.get("outputRoots", [])
        if root.get("enabled", True) and root.get("path")
    ]


def get_active_run(settings: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for row in list_runs(settings):
        if str(row.get("state", "")).lower() in {"pending", "running"}:
            return row
    return None


def find_run_dir(job_id: str, settings: dict[str, Any] | None = None) -> Path:
    settings = settings or load_settings()
    for root in _enabled_output_root_list(settings):
        candidate = Path(str(root["path"])) / job_id
        if candidate.exists():
            return candidate
    raise ValueError(f"Run not found: {job_id}")


def create_job(
    *,
    settings: dict[str, Any] | None = None,
    input_items: list[InputItem],
    output_root_id: str | None = None,
    reprocess_duplicates: bool = False,
) -> tuple[str, Path]:
    settings = settings or load_settings()
    active = get_active_run(settings)
    if active is not None:
        raise ValueError(f"Another job is already active: {active['job_id']}")
    if not input_items:
        raise ValueError("No input videos were selected.")

    output_root = _enabled_output_root(settings, output_root_id)
    output_root_path = Path(str(output_root["path"]))
    ensure_dir(output_root_path)

    job_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
    run_dir = output_root_path / job_id
    ensure_dir(run_dir / "media")
    ensure_dir(run_dir / "llm")
    ensure_dir(run_dir / "logs")

    request = JobRequest(
        schema_version=1,
        job_id=job_id,
        created_at=now_iso(),
        output_root_id=str(output_root.get("id") or "runs"),
        output_root_path=str(output_root_path),
        profile="quality-first",
        reprocess_duplicates=reprocess_duplicates,
        token_enabled=bool(load_huggingface_token()),
        input_items=input_items,
    )
    status = JobStatus(
        job_id=job_id,
        state="pending",
        current_stage="queued",
        message="Queued for worker pickup.",
        videos_total=len(input_items),
        updated_at=now_iso(),
    )
    result = JobResult(
        job_id=job_id,
        state="pending",
        run_dir=str(run_dir),
        output_root_id=str(output_root.get("id") or "runs"),
        output_root_path=str(output_root_path),
    )
    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "generated_at": now_iso(),
        "items": [],
    }

    (run_dir / "request.json").write_text(
        json.dumps(request.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "status.json").write_text(
        json.dumps(status.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_text(run_dir / "RUN_INFO.md", "# Run Info\n\nPending worker pickup.\n")
    write_text(
        run_dir / "TRANSCRIPTION_INFO.md", "# Transcription Info\n\nPending worker pickup.\n"
    )
    write_text(run_dir / "NOTICE.md", "# Notice\n\nPending worker pickup.\n")

    return job_id, run_dir


def settings_snapshot(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or load_settings()
    token = load_huggingface_token()
    return {
        "has_token": bool(token),
        "terms_confirmed": bool(settings.get("huggingfaceTermsConfirmed", False)),
        "ready": bool(token) and bool(settings.get("huggingfaceTermsConfirmed", False)),
        "input_roots": _enabled_input_roots(settings),
        "output_roots": _enabled_output_root_list(settings),
    }
