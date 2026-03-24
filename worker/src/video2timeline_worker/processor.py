from __future__ import annotations

import json
import traceback
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from .catalog import append_catalog_rows, load_catalog
from .config import ChangeDetectionConfig
from .contracts import JobRequest, JobResult, JobStatus, ManifestItem
from .ffmpeg_utils import extract_audio, probe_video, trim_audio
from .fs_utils import (
    append_log,
    ensure_dir,
    now_iso,
    read_json,
    short_id,
    slugify,
    tail_text,
    write_json_atomic,
    write_text,
)
from .hashing import sha256_file
from .screens import extract_screens
from .settings import load_settings
from .timeline import render_timeline
from .transcribe import transcribe_audio


def _job_log_path(job_dir: Path) -> Path:
    return job_dir / "logs" / "worker.log"


def _status_path(job_dir: Path) -> Path:
    return job_dir / "status.json"


def _result_path(job_dir: Path) -> Path:
    return job_dir / "result.json"


def _manifest_path(job_dir: Path) -> Path:
    return job_dir / "manifest.json"


def _request_path(job_dir: Path) -> Path:
    return job_dir / "request.json"


def _load_request(job_dir: Path) -> JobRequest:
    return JobRequest.from_dict(read_json(_request_path(job_dir)))


def _load_status(job_dir: Path) -> JobStatus:
    path = _status_path(job_dir)
    if not path.exists():
        return JobStatus(job_id=job_dir.name, updated_at=now_iso())
    return JobStatus(**read_json(path))


def _write_status(job_dir: Path, status: JobStatus) -> None:
    status.updated_at = now_iso()
    write_json_atomic(_status_path(job_dir), status.to_dict())


def _write_result(job_dir: Path, result: JobResult) -> None:
    write_json_atomic(_result_path(job_dir), result.to_dict())


def _write_manifest(job_dir: Path, job_id: str, items: list[ManifestItem]) -> None:
    payload = {
        "schema_version": 1,
        "job_id": job_id,
        "generated_at": now_iso(),
        "items": [item.to_dict() for item in items],
    }
    write_json_atomic(_manifest_path(job_dir), payload)


def _estimate_remaining(total_duration_sec: float, processed_duration_sec: float, elapsed_sec: float) -> float | None:
    if total_duration_sec <= 0 or processed_duration_sec <= 0 or elapsed_sec <= 0:
        return None
    rate = processed_duration_sec / elapsed_sec
    if rate <= 0:
        return None
    return max(0.0, (total_duration_sec - processed_duration_sec) / rate)


def _write_support_docs(job_dir: Path, request: JobRequest) -> None:
    run_info = "\n".join(
        [
            "# Run Info",
            "",
            f"- Job ID: `{request.job_id}`",
            f"- Created At: `{request.created_at}`",
            f"- Profile: `{request.profile}`",
            f"- Input Count: `{len(request.input_items)}`",
            f"- Reprocess Duplicates: `{request.reprocess_duplicates}`",
            "",
            "This run uses file-based coordination between the ASP.NET Core web app and the Python worker.",
            "",
        ]
    )
    transcription_info = "\n".join(
        [
            "# Transcription Info",
            "",
            "- Audio transcription: `whisperx` with `medium`, `ja`, CPU `int8`",
            "- Diarization: `pyannote` only when Hugging Face token and terms confirmation are available",
            "- OCR: `EasyOCR`",
            "- Image caption: `Florence-2 base` when available",
            "- Notes:",
            "  - `raw` outputs are preserved.",
            "  - OCR runs only for major visual changes.",
            "  - Screen text is summarized instead of emitting full OCR every time.",
            "",
        ]
    )
    notice = "\n".join(
        [
            "# Notice",
            "",
            "- This run is optimized for local processing, not cloud transcription.",
            "- Model downloads may happen on first use and are cached afterward.",
            "- If diarization prerequisites are missing, the worker continues without speaker separation.",
            "- Timeline timestamps are based on the original video time; silence trimming is tracked in `cut_map.json`.",
            "",
        ]
    )
    write_text(job_dir / "RUN_INFO.md", run_info)
    write_text(job_dir / "TRANSCRIPTION_INFO.md", transcription_info)
    write_text(job_dir / "NOTICE.md", notice)


def _resolve_input_path(item: Any) -> Path:
    if item.uploaded_path:
        return Path(item.uploaded_path)
    return Path(item.original_path)


def _make_media_id(item: Any, file_hash: str) -> str:
    stem = slugify(Path(item.display_name or Path(item.original_path).stem).stem)
    return f"{stem}-{file_hash[:8] or short_id()}"


def _collect_pending_jobs() -> list[Path]:
    settings = load_settings()
    rows: list[Path] = []
    for root in settings.get("outputRoots", []):
        if not root.get("enabled", True):
            continue
        root_path = Path(str(root.get("path") or ""))
        if not root_path.exists():
            continue
        for candidate in sorted(root_path.glob("run-*")):
            if not candidate.is_dir():
                continue
            if not _request_path(candidate).exists():
                continue
            status = _load_status(candidate)
            if status.state == "pending":
                rows.append(candidate)
    return rows


def _llm_export(job_dir: Path, processed_items: list[ManifestItem]) -> tuple[int, Path | None]:
    llm_dir = ensure_dir(job_dir / "llm")
    rows: list[dict[str, Any]] = []
    batch_contents: list[str] = []
    current_batch: list[str] = []
    current_size = 0
    max_batch_chars = 120_000

    for item in processed_items:
        if item.status != "completed" or not item.media_id:
            continue
        timeline_path = job_dir / "media" / item.media_id / "timeline" / "timeline.md"
        if not timeline_path.exists():
            continue
        row = {
            "job_id": job_dir.name,
            "media_id": item.media_id,
            "original_path": item.original_path,
            "timeline_path": str(timeline_path),
            "duration_seconds": item.duration_seconds,
            "sha256": item.sha256,
        }
        rows.append(row)
        timeline_text = timeline_path.read_text(encoding="utf-8", errors="replace").strip()
        block = "\n".join(
            [
                f"# Media: {item.media_id}",
                f"- Source: `{item.original_path}`",
                "",
                timeline_text,
                "",
            ]
        )
        if current_batch and current_size + len(block) > max_batch_chars:
            batch_contents.append("\n".join(current_batch).strip() + "\n")
            current_batch = []
            current_size = 0
        current_batch.append(block)
        current_size += len(block)

    if current_batch:
        batch_contents.append("\n".join(current_batch).strip() + "\n")

    index_path: Path | None = None
    if rows:
        index_path = llm_dir / "timeline_index.jsonl"
        index_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
    for idx, content in enumerate(batch_contents, start=1):
        write_text(llm_dir / f"batch-{idx:03d}.md", content)

    return len(batch_contents), index_path


def _process_one_item(
    *,
    job_dir: Path,
    request: JobRequest,
    item: Any,
    manifest_item: ManifestItem,
    thresholds: ChangeDetectionConfig,
    on_stage: Callable[[str, str], None] | None = None,
) -> None:
    source_path = _resolve_input_path(item)
    media_dir = ensure_dir(job_dir / "media" / str(manifest_item.media_id))
    audio_dir = ensure_dir(media_dir / "audio")
    transcript_dir = ensure_dir(media_dir / "transcript")
    screen_dir = ensure_dir(media_dir / "screen")
    timeline_dir = ensure_dir(media_dir / "timeline")

    source_info = {
        "job_id": request.job_id,
        "media_id": manifest_item.media_id,
        "input_id": item.input_id,
        "source_kind": item.source_kind,
        "source_id": item.source_id,
        "original_path": item.original_path,
        "resolved_path": str(source_path),
        "display_name": item.display_name,
        "size_bytes": manifest_item.size_bytes,
        "duration_seconds": manifest_item.duration_seconds,
        "sha256": manifest_item.sha256,
    }
    write_json_atomic(media_dir / "source.json", source_info)

    extracted_audio_path = audio_dir / "extracted.mp3"
    trimmed_audio_path = audio_dir / "trimmed.mp3"

    if on_stage:
        on_stage("extract_audio", "Extracting audio.")
    extract_audio(source_path, extracted_audio_path)
    if on_stage:
        on_stage("trim_silence", "Trimming silence and writing cut map.")
    cut_map = trim_audio(extracted_audio_path, trimmed_audio_path, manifest_item.duration_seconds)
    write_json_atomic(audio_dir / "cut_map.json", cut_map)

    if on_stage:
        on_stage("transcribe", "Running WhisperX transcription.")
    transcript_payload = transcribe_audio(
        source_name=item.display_name,
        trimmed_audio_path=trimmed_audio_path,
        transcript_dir=transcript_dir,
        cut_map=cut_map,
    )
    if on_stage:
        on_stage("screen_extract", "Extracting screenshots and OCR notes.")
    screen_notes, screen_diffs = extract_screens(
        video_path=source_path,
        screen_dir=screen_dir,
        duration_seconds=manifest_item.duration_seconds,
        thresholds=thresholds,
    )
    if on_stage:
        on_stage("timeline_render", "Rendering timeline markdown.")
    render_timeline(
        output_path=timeline_dir / "timeline.md",
        source_info=source_info,
        transcript_payload=transcript_payload,
        screen_notes=screen_notes,
        screen_diffs=screen_diffs,
    )


def process_job(job_dir: Path | None = None) -> bool:
    if job_dir is None:
        pending = _collect_pending_jobs()
        if not pending:
            return False
        job_dir = pending[0]

    job_dir = job_dir.resolve()
    if not _request_path(job_dir).exists():
        return False

    log_path = _job_log_path(job_dir)
    request = _load_request(job_dir)
    _write_support_docs(job_dir, request)

    status = _load_status(job_dir)
    status.job_id = request.job_id
    status.state = "running"
    status.current_stage = "preflight"
    status.message = "Preparing job."
    status.started_at = status.started_at or now_iso()
    _write_status(job_dir, status)

    result = JobResult(
        job_id=request.job_id,
        state="running",
        run_dir=str(job_dir),
        output_root_id=request.output_root_id,
        output_root_path=request.output_root_path,
    )
    _write_result(job_dir, result)

    started = monotonic()
    warnings: list[str] = []
    catalog = load_catalog(Path(request.output_root_path))
    manifest_items: list[ManifestItem] = []
    appended_catalog_rows: list[dict[str, Any]] = []

    try:
        append_log(log_path, f"[{now_iso()}] Starting job {request.job_id}")
        for index, input_item in enumerate(request.input_items, start=1):
            status.current_media = input_item.display_name
            status.message = f"Preflight {index}/{len(request.input_items)}: {input_item.display_name}"
            _write_status(job_dir, status)
            source_path = _resolve_input_path(input_item)
            media_probe = probe_video(source_path)
            file_hash = sha256_file(source_path)
            duplicate = catalog.get(file_hash)
            duplicate_status = "new"
            duplicate_of = None
            if duplicate:
                duplicate_of = str(duplicate.get("media_id") or duplicate.get("timeline_path") or duplicate.get("run_dir") or "")
                duplicate_status = "duplicate_reprocess" if request.reprocess_duplicates else "duplicate_skip"

            manifest_items.append(
                ManifestItem(
                    input_id=input_item.input_id,
                    source_kind=input_item.source_kind,
                    original_path=input_item.original_path,
                    file_name=Path(input_item.original_path).name,
                    size_bytes=int(media_probe["size_bytes"]),
                    duration_seconds=float(media_probe["duration_seconds"]),
                    sha256=file_hash,
                    duplicate_status=duplicate_status,
                    duplicate_of=duplicate_of or None,
                    media_id=_make_media_id(input_item, file_hash),
                    status="queued",
                )
            )

        total_duration = sum(item.duration_seconds for item in manifest_items)
        status.videos_total = len(manifest_items)
        status.total_duration_sec = round(total_duration, 3)
        status.current_media = None
        status.message = "Preflight completed."
        _write_manifest(job_dir, request.job_id, manifest_items)
        _write_status(job_dir, status)
        append_log(log_path, f"[{now_iso()}] Preflight complete for {len(manifest_items)} item(s).")

        thresholds = ChangeDetectionConfig()
        completed_items: list[ManifestItem] = []
        for index, (input_item, manifest_item) in enumerate(zip(request.input_items, manifest_items, strict=False), start=1):
            status.current_media = input_item.display_name
            status.current_media_elapsed_sec = 0.0
            status.current_stage = "processing"
            status.message = f"Processing {index}/{len(manifest_items)}: {input_item.display_name}"
            _write_status(job_dir, status)
            item_started = monotonic()

            def stage_update(stage_name: str, message: str) -> None:
                status.current_stage = stage_name
                status.message = message
                status.current_media = input_item.display_name
                status.current_media_elapsed_sec = round(monotonic() - item_started, 3)
                _write_status(job_dir, status)
                append_log(log_path, f"[{now_iso()}] {stage_name}: {input_item.original_path}")

            if manifest_item.duplicate_status == "duplicate_skip":
                manifest_item.status = "skipped_duplicate"
                status.videos_skipped += 1
                status.processed_duration_sec = round(status.processed_duration_sec + manifest_item.duration_seconds, 3)
                status.estimated_remaining_sec = _estimate_remaining(
                    status.total_duration_sec,
                    status.processed_duration_sec,
                    monotonic() - started,
                )
                _write_manifest(job_dir, request.job_id, manifest_items)
                _write_status(job_dir, status)
                append_log(log_path, f"[{now_iso()}] Skipped duplicate: {input_item.original_path}")
                continue

            try:
                _process_one_item(
                    job_dir=job_dir,
                    request=request,
                    item=input_item,
                    manifest_item=manifest_item,
                    thresholds=thresholds,
                    on_stage=stage_update,
                )
                manifest_item.status = "completed"
                completed_items.append(manifest_item)
                appended_catalog_rows.append(
                    {
                        "job_id": request.job_id,
                        "run_dir": str(job_dir),
                        "media_id": manifest_item.media_id,
                        "sha256": manifest_item.sha256,
                        "original_path": manifest_item.original_path,
                        "duration_seconds": manifest_item.duration_seconds,
                        "timeline_path": str(job_dir / "media" / str(manifest_item.media_id) / "timeline" / "timeline.md"),
                        "created_at": now_iso(),
                    }
                )
                status.videos_done += 1
                append_log(log_path, f"[{now_iso()}] Completed: {input_item.original_path}")
            except Exception as exc:
                manifest_item.status = "failed"
                status.videos_failed += 1
                warnings.append(f"{input_item.display_name}: {exc}")
                append_log(log_path, f"[{now_iso()}] Failed: {input_item.original_path}")
                append_log(log_path, traceback.format_exc())

            status.processed_duration_sec = round(status.processed_duration_sec + manifest_item.duration_seconds, 3)
            status.current_media_elapsed_sec = round(monotonic() - item_started, 3)
            status.estimated_remaining_sec = _estimate_remaining(
                status.total_duration_sec,
                status.processed_duration_sec,
                monotonic() - started,
            )
            _write_manifest(job_dir, request.job_id, manifest_items)
            _write_status(job_dir, status)

        if appended_catalog_rows:
            append_catalog_rows(Path(request.output_root_path), appended_catalog_rows)

        status.current_stage = "llm_export"
        status.message = "Building timeline batches."
        status.current_media = None
        status.current_media_elapsed_sec = 0.0
        _write_status(job_dir, status)
        batch_count, timeline_index_path = _llm_export(job_dir, completed_items)

        result.state = "completed" if status.videos_failed == 0 else "completed"
        result.processed_count = status.videos_done
        result.skipped_count = status.videos_skipped
        result.error_count = status.videos_failed
        result.batch_count = batch_count
        result.timeline_index_path = str(timeline_index_path) if timeline_index_path else None
        result.warnings = warnings
        _write_result(job_dir, result)

        status.state = "completed"
        status.current_stage = "completed"
        status.message = "Job completed."
        status.warnings = warnings
        status.current_media = None
        status.current_media_elapsed_sec = 0.0
        status.estimated_remaining_sec = 0.0
        status.completed_at = now_iso()
        _write_status(job_dir, status)
        append_log(log_path, f"[{now_iso()}] Job completed with {status.videos_done} processed, {status.videos_skipped} skipped, {status.videos_failed} failed.")
        return True
    except Exception as exc:
        append_log(log_path, f"[{now_iso()}] Job failed: {exc}")
        append_log(log_path, traceback.format_exc())
        status.state = "failed"
        status.current_stage = "failed"
        status.message = str(exc)
        status.warnings = warnings
        status.completed_at = now_iso()
        _write_status(job_dir, status)
        result.state = "failed"
        result.processed_count = status.videos_done
        result.skipped_count = status.videos_skipped
        result.error_count = status.videos_failed + 1
        result.warnings = warnings + [tail_text(log_path, max_lines=30)]
        _write_result(job_dir, result)
        return True
