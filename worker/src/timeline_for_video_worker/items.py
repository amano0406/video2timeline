from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any
import zipfile

from . import __version__
from .discovery import VideoFile, resolve_configured_path
from .probe import canonical_json, probe_video_files, sha256_hex, utc_now_iso
from .settings import PRODUCT_NAME


VIDEO_RECORD_SCHEMA_VERSION = "timeline_for_video.video_record.v1"
TIMELINE_SCHEMA_VERSION = "timeline_for_video.timeline.v1"
CONVERT_INFO_SCHEMA_VERSION = "timeline_for_video.convert_info.v1"
ITEM_REFRESH_RESULT_SCHEMA_VERSION = "timeline_for_video.item_refresh_result.v1"
ITEM_LIST_RESULT_SCHEMA_VERSION = "timeline_for_video.item_list_result.v1"
ITEM_DOWNLOAD_RESULT_SCHEMA_VERSION = "timeline_for_video.item_download_result.v1"
ITEM_REMOVE_RESULT_SCHEMA_VERSION = "timeline_for_video.item_remove_result.v1"
PIPELINE_VERSION = "timeline_for_video.pipeline.m5"


def refresh_items(
    video_files: list[VideoFile],
    output_root_text: str,
    ffprobe_bin: str = "ffprobe",
    max_items: int | None = None,
) -> dict[str, Any]:
    if max_items is not None and max_items < 1:
        raise ValueError("max_items must be at least 1")

    generated_at = utc_now_iso()
    output_root = resolve_configured_path(output_root_text)
    probe_result = probe_video_files(video_files, ffprobe_bin=ffprobe_bin, max_items=max_items)
    records: list[dict[str, Any]] = []

    for probe_record in probe_result["records"]:
        records.append(refresh_probe_record(probe_record, output_root, output_root_text, generated_at))

    failed_items = sum(1 for record in records if not record["ok"])
    return {
        "schemaVersion": ITEM_REFRESH_RESULT_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": __version__,
        "generatedAt": generated_at,
        "ok": failed_items == 0,
        "outputRoot": {
            "configuredPath": output_root_text,
            "resolvedPath": str(output_root),
        },
        "ffprobeVersion": probe_result["ffprobeVersion"],
        "counts": {
            "discoveredFiles": len(video_files),
            "refreshedItems": len(records),
            "failedItems": failed_items,
            "skippedByMaxItems": probe_result["counts"]["skippedByMaxItems"],
        },
        "records": records,
    }


def refresh_probe_record(
    probe_record: dict[str, Any],
    output_root: Path,
    output_root_text: str,
    generated_at: str,
) -> dict[str, Any]:
    item_id = probe_record["itemId"]
    item_root = output_root / "items" / item_id
    raw_outputs_dir = item_root / "raw_outputs"
    artifacts_dir = item_root / "artifacts"
    frames_dir = artifacts_dir / "frames"
    ffprobe_path = raw_outputs_dir / "ffprobe.json"
    frame_samples_path = raw_outputs_dir / "frame_samples.json"
    contact_sheet_path = artifacts_dir / "contact_sheet.jpg"
    video_record_path = item_root / "video_record.json"
    timeline_path = item_root / "timeline.json"
    convert_info_path = item_root / "convert_info.json"

    frame_samples, frame_samples_warning = read_optional_json(frame_samples_path)
    warnings = list(probe_record.get("recordSeed", {}).get("processing", {}).get("warnings", []))
    if frame_samples_warning:
        warnings.append(frame_samples_warning)

    paths = {
        "itemRoot": str(item_root),
        "videoRecordJson": str(video_record_path),
        "timelineJson": str(timeline_path),
        "convertInfoJson": str(convert_info_path),
        "rawOutputsDir": str(raw_outputs_dir),
        "ffprobeJson": str(ffprobe_path),
        "frameSamplesJson": str(frame_samples_path),
        "artifactsDir": str(artifacts_dir),
        "framesDir": str(frames_dir),
        "contactSheet": str(contact_sheet_path),
        "outputRootConfiguredPath": output_root_text,
    }

    raw_outputs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    write_json(ffprobe_path, probe_record)

    video_record = build_video_record(probe_record, frame_samples, paths, generated_at, warnings)
    timeline = build_timeline(probe_record, frame_samples, paths, generated_at)
    convert_info = build_convert_info(probe_record, frame_samples, paths, generated_at, warnings)

    write_json(video_record_path, video_record)
    write_json(timeline_path, timeline)
    write_json(convert_info_path, convert_info)

    return {
        "itemId": item_id,
        "ok": probe_record["ffprobe"]["ok"],
        "sourcePath": probe_record["sourceIdentity"]["sourcePath"],
        "itemRoot": str(item_root),
        "outputFiles": output_file_entries(paths),
        "counts": {
            "frames": len(video_record["frames"]),
            "visualEvents": len(timeline["lanes"]["visual"]),
            "audioEvents": len(timeline["lanes"]["audio"]),
        },
        "warnings": warnings,
    }


def build_video_record(
    probe_record: dict[str, Any],
    frame_samples: dict[str, Any] | None,
    paths: dict[str, str],
    generated_at: str,
    warnings: list[str],
) -> dict[str, Any]:
    summary = probe_record["ffprobe"]["summary"]
    frames = frame_entries(frame_samples)
    contact_sheet_exists = Path(paths["contactSheet"]).exists()
    return {
        "schema_version": VIDEO_RECORD_SCHEMA_VERSION,
        "record_id": probe_record["itemId"],
        "asset": {
            "source_path": probe_record["sourceIdentity"]["sourcePath"],
            "source_fingerprint": probe_record["sourceFingerprint"]["value"],
            "source_identity": probe_record["sourceIdentity"],
            "source_video_modified": False,
        },
        "timeline": {
            "coordinate": "source_video_relative_time",
            "timeline_json": paths["timelineJson"],
        },
        "video": {
            "format": summary["format"] if summary else None,
            "streams": [stream for stream in summary["streams"] if stream["codecType"] == "video"] if summary else [],
        },
        "audio": {
            "streams": [stream for stream in summary["streams"] if stream["codecType"] == "audio"] if summary else [],
        },
        "processing": {
            "stage": "item_refresh",
            "pipeline_version": PIPELINE_VERSION,
            "generated_at": generated_at,
            "source_video_modified": False,
            "raw_outputs": {
                "ffprobe_json": paths["ffprobeJson"],
                "frame_samples_json": paths["frameSamplesJson"],
            },
            "artifacts": {
                "contact_sheet": paths["contactSheet"],
                "frames_dir": paths["framesDir"],
            },
            "warnings": warnings,
        },
        "segments": [],
        "frames": frames,
        "text": {
            "mode": "not_implemented_in_v1",
            "ocr": False,
            "transcription": False,
        },
        "review": {
            "contact_sheet": paths["contactSheet"],
            "contact_sheet_exists": contact_sheet_exists,
            "frame_count": len(frames),
        },
    }


def build_timeline(
    probe_record: dict[str, Any],
    frame_samples: dict[str, Any] | None,
    paths: dict[str, str],
    generated_at: str,
) -> dict[str, Any]:
    summary = probe_record["ffprobe"]["summary"]
    duration_sec = summary["format"]["durationSec"] if summary else None
    visual_events: list[dict[str, Any]] = [
        {
            "eventType": "video_observed",
            "timeSec": 0.0,
            "sourcePath": probe_record["sourceIdentity"]["sourcePath"],
            "ffprobeJson": paths["ffprobeJson"],
        },
        {
            "eventType": "video_interval",
            "startSec": 0.0,
            "endSec": duration_sec,
            "durationSec": duration_sec,
        },
    ]

    for frame in frame_entries(frame_samples):
        visual_events.append(
            {
                "eventType": "frame_sample",
                "timeSec": frame["time_sec"],
                "frameId": frame["frame_id"],
                "artifactPath": frame["artifact_path"],
                "ok": frame["ok"],
            }
        )

    audio_streams = [stream for stream in summary["streams"] if stream["codecType"] == "audio"] if summary else []
    audio_events = [
        {
            "eventType": "audio_reference",
            "startSec": 0.0,
            "endSec": duration_sec,
            "streamCount": len(audio_streams),
        }
    ]

    return {
        "schemaVersion": TIMELINE_SCHEMA_VERSION,
        "itemId": probe_record["itemId"],
        "generatedAt": generated_at,
        "timelineCoordinate": "source_video_relative_time",
        "sourceFingerprint": probe_record["sourceFingerprint"]["value"],
        "durationSec": duration_sec,
        "lanes": {
            "visual": visual_events,
            "audio": audio_events,
        },
    }


def build_convert_info(
    probe_record: dict[str, Any],
    frame_samples: dict[str, Any] | None,
    paths: dict[str, str],
    generated_at: str,
    warnings: list[str],
) -> dict[str, Any]:
    summary = probe_record["ffprobe"]["summary"]
    output_files = output_file_entries(paths)
    signature_material = {
        "itemId": probe_record["itemId"],
        "sourceFingerprint": probe_record["sourceFingerprint"]["value"],
        "pipelineVersion": PIPELINE_VERSION,
        "productVersion": __version__,
        "outputFiles": output_files,
    }
    frame_count = len(frame_entries(frame_samples))
    return {
        "schemaVersion": CONVERT_INFO_SCHEMA_VERSION,
        "product": {
            "name": PRODUCT_NAME,
            "version": __version__,
        },
        "generatedAt": generated_at,
        "sourceFingerprint": probe_record["sourceFingerprint"],
        "sourceFileIdentity": probe_record["sourceIdentity"],
        "ffprobeVersion": probe_record["ffprobe"]["version"],
        "pipelineVersion": PIPELINE_VERSION,
        "generationSignature": "sha256:" + sha256_hex(canonical_json(signature_material)),
        "samplingParameters": frame_samples.get("samplingParameters") if frame_samples else None,
        "outputFiles": output_files,
        "counts": {
            "videoStreams": summary["counts"]["videoStreams"] if summary else 0,
            "audioStreams": summary["counts"]["audioStreams"] if summary else 0,
            "frames": frame_count,
            "warnings": len(warnings),
        },
        "warnings": warnings,
        "source_video_modified": False,
    }


def list_items(output_root_text: str) -> dict[str, Any]:
    output_root = resolve_configured_path(output_root_text)
    items_root = output_root / "items"
    items: list[dict[str, Any]] = []

    if items_root.is_dir():
        for item_dir in sorted((path for path in items_root.iterdir() if path.is_dir()), key=lambda path: path.name):
            record_path = item_dir / "video_record.json"
            record, warning = read_optional_json(record_path)
            if record is None:
                items.append(
                    {
                        "itemId": item_dir.name,
                        "ok": False,
                        "itemRoot": str(item_dir),
                        "videoRecordJson": str(record_path),
                        "sourcePath": None,
                        "durationSec": None,
                        "frameCount": 0,
                        "contactSheet": None,
                        "warnings": [warning or "video_record_missing"],
                    }
                )
                continue

            items.append(item_summary(item_dir, record_path, record))

    return {
        "schemaVersion": ITEM_LIST_RESULT_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": __version__,
        "ok": True,
        "outputRoot": {
            "configuredPath": output_root_text,
            "resolvedPath": str(output_root),
        },
        "counts": {
            "items": len(items),
        },
        "items": items,
    }


def download_items(output_root_text: str) -> dict[str, Any]:
    generated_at = utc_now_iso()
    output_root = resolve_configured_path(output_root_text)
    downloads_dir = output_root / "downloads"
    latest_dir = output_root / "latest"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    item_dirs = item_roots(output_root)
    archive_name = f"timeline-for-video-items-{timestamp_slug(generated_at)}.zip"
    archive_path = downloads_dir / archive_name
    latest_archive_path = latest_dir / "items.zip"
    latest_manifest_path = latest_dir / "download_manifest.json"
    output_files = [
        {"kind": "download_zip", "path": str(archive_path), "exists": True},
        {"kind": "latest_zip", "path": str(latest_archive_path), "exists": True},
        {"kind": "latest_manifest", "path": str(latest_manifest_path), "exists": True},
    ]
    manifest = {
        "schemaVersion": ITEM_DOWNLOAD_RESULT_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": __version__,
        "generatedAt": generated_at,
        "sourceVideosIncluded": False,
        "outputFiles": output_files,
        "items": [],
        "files": [],
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item_dir in item_dirs:
            item_files = [path for path in generated_item_files(item_dir) if path.is_file()]
            manifest["items"].append(
                {
                    "itemId": item_dir.name,
                    "itemRoot": str(item_dir),
                    "fileCount": len(item_files),
                }
            )
            for path in item_files:
                archive_path_text = path.relative_to(output_root).as_posix()
                archive.write(path, archive_path_text)
                manifest["files"].append(
                    {
                        "path": str(path),
                        "archivePath": archive_path_text,
                        "sizeBytes": path.stat().st_size,
                    }
                )
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    shutil.copy2(archive_path, latest_archive_path)
    write_json(latest_manifest_path, manifest)

    return {
        "schemaVersion": ITEM_DOWNLOAD_RESULT_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": __version__,
        "generatedAt": generated_at,
        "ok": True,
        "outputRoot": {
            "configuredPath": output_root_text,
            "resolvedPath": str(output_root),
        },
        "archivePath": str(archive_path),
        "latestArchivePath": str(latest_archive_path),
        "latestManifestPath": str(latest_manifest_path),
        "sourceVideosIncluded": False,
        "counts": {
            "items": len(item_dirs),
            "files": len(manifest["files"]),
            "bytes": archive_path.stat().st_size,
        },
        "outputFiles": output_files,
        "items": manifest["items"],
    }


def remove_items(output_root_text: str, dry_run: bool = False) -> dict[str, Any]:
    output_root = resolve_configured_path(output_root_text)
    targets = removal_targets(output_root)
    deleted_files: list[str] = []
    skipped_files: list[str] = []
    pruned_dirs: list[str] = []
    skipped_dirs: list[str] = []

    if not dry_run:
        for path in targets["files"]:
            if not safe_generated_path(output_root, path) or path.is_symlink():
                skipped_files.append(str(path))
                continue
            try:
                path.unlink()
                deleted_files.append(str(path))
            except FileNotFoundError:
                continue
            except OSError:
                skipped_files.append(str(path))

        for path in targets["directories"]:
            if not safe_generated_path(output_root, path) or path.is_symlink():
                skipped_dirs.append(str(path))
                continue
            try:
                path.rmdir()
                pruned_dirs.append(str(path))
            except FileNotFoundError:
                continue
            except OSError:
                skipped_dirs.append(str(path))

    return {
        "schemaVersion": ITEM_REMOVE_RESULT_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": __version__,
        "generatedAt": utc_now_iso(),
        "ok": not skipped_files and not skipped_dirs,
        "dryRun": dry_run,
        "outputRoot": {
            "configuredPath": output_root_text,
            "resolvedPath": str(output_root),
        },
        "sourceVideosRemoved": False,
        "counts": {
            "targetFiles": len(targets["files"]),
            "targetDirectories": len(targets["directories"]),
            "deletedFiles": len(deleted_files),
            "prunedDirectories": len(pruned_dirs),
            "skippedFiles": len(skipped_files),
            "skippedDirectories": len(skipped_dirs),
        },
        "targets": {
            "files": [str(path) for path in targets["files"]],
            "directories": [str(path) for path in targets["directories"]],
        },
        "deletedFiles": deleted_files,
        "prunedDirectories": pruned_dirs,
        "skippedFiles": skipped_files,
        "skippedDirectories": skipped_dirs,
    }


def item_summary(item_dir: Path, record_path: Path, record: dict[str, Any]) -> dict[str, Any]:
    asset = record.get("asset") if isinstance(record.get("asset"), dict) else {}
    video_format = record.get("video", {}).get("format") if isinstance(record.get("video"), dict) else None
    frames = record.get("frames") if isinstance(record.get("frames"), list) else []
    review = record.get("review") if isinstance(record.get("review"), dict) else {}
    processing = record.get("processing") if isinstance(record.get("processing"), dict) else {}
    warnings = processing.get("warnings") if isinstance(processing.get("warnings"), list) else []
    return {
        "itemId": record.get("record_id") or item_dir.name,
        "ok": True,
        "itemRoot": str(item_dir),
        "videoRecordJson": str(record_path),
        "sourcePath": asset.get("source_path"),
        "durationSec": video_format.get("durationSec") if isinstance(video_format, dict) else None,
        "frameCount": len(frames),
        "contactSheet": review.get("contact_sheet"),
        "warnings": warnings,
    }


def item_roots(output_root: Path) -> list[Path]:
    items_root = output_root / "items"
    if not items_root.is_dir():
        return []
    return sorted((path for path in items_root.iterdir() if path.is_dir()), key=lambda path: path.name)


def generated_item_files(item_dir: Path) -> list[Path]:
    frames_dir = item_dir / "artifacts" / "frames"
    files = [
        item_dir / "video_record.json",
        item_dir / "timeline.json",
        item_dir / "convert_info.json",
        item_dir / "raw_outputs" / "ffprobe.json",
        item_dir / "raw_outputs" / "frame_samples.json",
        item_dir / "artifacts" / "contact_sheet.jpg",
    ]
    if frames_dir.is_dir():
        files.extend(sorted(frames_dir.glob("frame-*.jpg")))
    return files


def removal_targets(output_root: Path) -> dict[str, list[Path]]:
    files: list[Path] = []
    directories: list[Path] = []

    for item_dir in item_roots(output_root):
        files.extend(path for path in generated_item_files(item_dir) if path.exists())
        directories.extend(
            [
                item_dir / "artifacts" / "frames",
                item_dir / "artifacts",
                item_dir / "raw_outputs",
                item_dir,
            ]
        )

    downloads_dir = output_root / "downloads"
    if downloads_dir.is_dir():
        files.extend(sorted(downloads_dir.glob("timeline-for-video-items-*.zip")))
        directories.append(downloads_dir)

    latest_dir = output_root / "latest"
    if latest_dir.is_dir():
        files.extend(
            path
            for path in [
                latest_dir / "items.zip",
                latest_dir / "download_manifest.json",
            ]
            if path.exists()
        )
        directories.append(latest_dir)

    items_dir = output_root / "items"
    if items_dir.is_dir():
        directories.append(items_dir)

    return {
        "files": unique_existing_paths(files),
        "directories": sorted(unique_existing_paths(directories), key=lambda path: len(path.parts), reverse=True),
    }


def unique_existing_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        unique.append(path)
    return unique


def safe_generated_path(output_root: Path, path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(output_root.resolve(strict=False))
    except ValueError:
        return False
    return True


def timestamp_slug(value: str) -> str:
    return (
        value.replace("+00:00", "Z")
        .replace("-", "")
        .replace(":", "")
        .replace(".", "")
    )


def frame_entries(frame_samples: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not frame_samples:
        return []

    frames_raw = frame_samples.get("frames")
    if not isinstance(frames_raw, list):
        return []

    frames: list[dict[str, Any]] = []
    for raw in frames_raw:
        if not isinstance(raw, dict):
            continue
        frames.append(
            {
                "frame_id": raw.get("frameId"),
                "time_sec": raw.get("timeSec"),
                "ok": bool(raw.get("ok")),
                "artifact_path": raw.get("outputPath"),
                "source": "frame_samples",
            }
        )
    return frames


def output_file_entries(paths: dict[str, str]) -> list[dict[str, Any]]:
    keys = [
        ("video_record", "videoRecordJson"),
        ("timeline", "timelineJson"),
        ("convert_info", "convertInfoJson"),
        ("ffprobe_raw", "ffprobeJson"),
        ("frame_samples", "frameSamplesJson"),
        ("contact_sheet", "contactSheet"),
        ("frames_dir", "framesDir"),
    ]
    written_by_refresh = {"video_record", "timeline", "convert_info", "ffprobe_raw"}
    return [
        {
            "kind": kind,
            "path": paths[key],
            "exists": True if kind in written_by_refresh else Path(paths[key]).exists(),
        }
        for kind, key in keys
    ]


def read_optional_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except json.JSONDecodeError:
        return None, f"invalid_json:{path.name}"

    if not isinstance(payload, dict):
        return None, f"json_root_not_object:{path.name}"
    return payload, None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
