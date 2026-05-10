from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any

from . import __version__
from .audio_models import run_audio_reference_models
from .discovery import VideoFile, resolve_configured_path
from .probe import command_prefix, probe_video_files, utc_now_iso
from .settings import PRODUCT_NAME


AUDIO_ANALYSIS_SCHEMA_VERSION = "timeline_for_video.audio_analysis.v1"
AUDIO_ANALYSIS_RESULT_SCHEMA_VERSION = "timeline_for_video.audio_analysis_result.v1"
AUDIO_DERIVATIVE_NAME = "source_audio.mp3"
AUDIO_PROCESSING_DIR_NAME = ".processing"
AUDIO_MODEL_INPUT_NAME = "normalized_audio.wav"
SILENCE_DETECT_BACKEND = "ffmpeg-silencedetect"
SILENCE_DETECT_MODEL_ID = "ffmpeg-silencedetect-noise-35db"
SILENCE_NOISE = "-35dB"
SILENCE_DURATION_SEC = 0.35
MIN_FFMPEG_TIMEOUT_SEC = 180
MAX_FFMPEG_TIMEOUT_SEC = 3600
FFMPEG_TIMEOUT_DURATION_DIVISOR = 90
FFMPEG_TIMEOUT_MARGIN_SEC = 120

# These identifiers intentionally match the current TimelineForAudio behavior.
# TimelineForVideo does not import or share that implementation.
AUDIO_REFERENCE_DIARIZATION_MODEL_ID = "pyannote/speaker-diarization-community-1"
AUDIO_REFERENCE_ACOUSTIC_UNIT_BACKEND = "zipa-large-crctc-300k-onnx-v1"
AUDIO_REFERENCE_ACOUSTIC_UNIT_MODEL_ID = "anyspeech/zipa-large-crctc-300k"
AUDIO_REFERENCE_ACOUSTIC_UNIT_TYPE = "phone_like"


def analyze_audio_files(
    video_files: list[VideoFile],
    output_root_text: str,
    ffprobe_bin: str = "ffprobe",
    ffmpeg_bin: str = "ffmpeg",
    max_items: int | None = None,
    settings: dict[str, Any] | None = None,
    audio_model_mode: str | None = None,
) -> dict[str, Any]:
    if max_items is not None and max_items < 1:
        raise ValueError("max_items must be at least 1")

    generated_at = utc_now_iso()
    output_root = resolve_configured_path(output_root_text)
    probe_result = probe_video_files(video_files, ffprobe_bin=ffprobe_bin, max_items=max_items)
    records = [
        analyze_probe_record_audio(
            probe_record,
            output_root=output_root,
            output_root_text=output_root_text,
            ffmpeg_bin=ffmpeg_bin,
            generated_at=generated_at,
            settings=settings or {},
            audio_model_mode=audio_model_mode,
        )
        for probe_record in probe_result["records"]
    ]
    failed_items = sum(1 for record in records if not record["ok"])
    return {
        "schemaVersion": AUDIO_ANALYSIS_RESULT_SCHEMA_VERSION,
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
            "processedItems": len(records),
            "failedItems": failed_items,
            "skippedByMaxItems": probe_result["counts"]["skippedByMaxItems"],
            "audioArtifacts": sum(1 for record in records if record["audioArtifact"]["ok"]),
            "speechCandidates": sum(record["speechActivity"]["counts"]["speechCandidates"] for record in records),
            "audioModelRuns": sum(1 for record in records if record["audioModels"]["mode"] != "off"),
            "diarizationTurns": sum(model_turn_count(record["diarization"]) for record in records),
            "acousticUnitTurns": sum(model_turn_count(record["acousticUnits"]) for record in records),
        },
        "records": records,
    }


def analyze_probe_record_audio(
    probe_record: dict[str, Any],
    output_root: Path,
    output_root_text: str,
    ffmpeg_bin: str,
    generated_at: str,
    settings: dict[str, Any],
    audio_model_mode: str | None,
) -> dict[str, Any]:
    item_id = probe_record["itemId"]
    item_root = output_root / "items" / item_id
    raw_outputs_dir = item_root / "raw_outputs"
    audio_artifacts_dir = item_root / "artifacts" / "audio"
    audio_analysis_path = raw_outputs_dir / "audio_analysis.json"
    audio_artifact_path = audio_artifacts_dir / AUDIO_DERIVATIVE_NAME
    audio_model_input_path = audio_artifacts_dir / AUDIO_PROCESSING_DIR_NAME / AUDIO_MODEL_INPUT_NAME
    warnings: list[str] = []

    summary = probe_record["ffprobe"]["summary"]
    audio_streams = [stream for stream in summary["streams"] if stream["codecType"] == "audio"] if summary else []
    duration_sec = summary["format"]["durationSec"] if summary else None

    record = {
        "schemaVersion": AUDIO_ANALYSIS_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": __version__,
        "generatedAt": generated_at,
        "itemId": item_id,
        "ok": False,
        "sourceVideoModified": False,
        "sourceIdentity": probe_record["sourceIdentity"],
        "sourceFingerprint": probe_record["sourceFingerprint"],
        "outputRoot": {
            "configuredPath": output_root_text,
            "itemRoot": str(item_root),
        },
        "inputs": {
            "ffprobeOk": probe_record["ffprobe"]["ok"],
            "audioStreamCount": len(audio_streams),
            "durationSec": duration_sec,
        },
        "audioArtifact": {
            "ok": False,
            "kind": "mp3_audio_derivative",
            "path": str(audio_artifact_path),
            "sourceVideoModified": False,
            "includedInDownloadZip": False,
            "command": [],
            "error": None,
        },
        "audioModelInput": {
            "ok": False,
            "kind": "temporary_normalized_wav",
            "path": str(audio_model_input_path),
            "retained": False,
            "removedAfterProcessing": False,
            "sourceVideoModified": False,
            "includedInDownloadZip": False,
            "command": [],
            "error": None,
        },
        "speechActivity": {
            "backend": SILENCE_DETECT_BACKEND,
            "modelId": SILENCE_DETECT_MODEL_ID,
            "parameters": {
                "noise": SILENCE_NOISE,
                "durationSec": SILENCE_DURATION_SEC,
            },
            "ok": False,
            "command": [],
            "silences": [],
            "speechCandidates": [],
            "counts": {
                "silences": 0,
                "speechCandidates": 0,
            },
            "error": None,
        },
        "diarization": {
            "status": "not_run",
            "model_id": AUDIO_REFERENCE_DIARIZATION_MODEL_ID,
            "requiredByReferenceProduct": True,
            "turn_count": 0,
            "warning_count": 1,
            "turns": [],
            "warnings": [
                "TimelineForVideo runs compatible audio models only when prerequisites are available."
            ],
        },
        "acousticUnits": {
            "status": "not_run",
            "backend": AUDIO_REFERENCE_ACOUSTIC_UNIT_BACKEND,
            "model_id": AUDIO_REFERENCE_ACOUSTIC_UNIT_MODEL_ID,
            "unit_type": AUDIO_REFERENCE_ACOUSTIC_UNIT_TYPE,
            "turn_count": 0,
            "warning_count": 1,
            "turns": [],
            "warnings": [
                "TimelineForVideo runs compatible acoustic-unit extraction only when prerequisites are available."
            ],
        },
        "text": {
            "mode": "audio_reference_units",
            "readableText": "",
            "segments": [],
            "warnings": [
                "TimelineForAudio currently stores phone-like acoustic units, not readable prose transcripts."
            ],
        },
        "audioModels": {
            "mode": audio_model_mode or "required",
            "ok": True,
            "warnings": [],
        },
        "warnings": warnings,
        "outputs": {
            "audioAnalysisJson": str(audio_analysis_path),
            "audioArtifactsDir": str(audio_artifacts_dir),
        },
    }

    raw_outputs_dir.mkdir(parents=True, exist_ok=True)
    if not probe_record["ffprobe"]["ok"]:
        warnings.append("ffprobe_failed")
        record["audioArtifact"]["error"] = "ffprobe failed"
        return write_audio_analysis(record, audio_analysis_path)
    if not audio_streams:
        warnings.append("no_audio_streams")
        configured_mode = str(audio_model_mode or "required").strip().casefold()
        model_result = run_audio_reference_models(
            audio_path=audio_model_input_path,
            speech_candidates=[],
            source_name=probe_record["sourceIdentity"]["sourcePath"],
            settings=settings,
            mode="required" if configured_mode == "required" else "off",
        )
        record["audioModels"] = model_result
        record["diarization"] = model_result["diarization"]
        record["acousticUnits"] = model_result["acousticUnits"]
        record["text"] = model_result["text"]
        warnings.extend(model_result.get("warnings", []))
        record["ok"] = model_result["ok"]
        return write_audio_analysis(record, audio_analysis_path)

    extract_result = run_audio_extract(
        probe_record["sourceIdentity"]["resolvedPath"],
        audio_artifact_path,
        ffmpeg_bin=ffmpeg_bin,
        duration_sec=duration_sec,
    )
    record["audioArtifact"].update(extract_result)
    if not extract_result["ok"]:
        warnings.append("audio_extract_failed")

    model_input_result = run_normalized_audio_extract(
        probe_record["sourceIdentity"]["resolvedPath"],
        audio_model_input_path,
        ffmpeg_bin=ffmpeg_bin,
        duration_sec=duration_sec,
    )
    record["audioModelInput"].update(model_input_result)
    if not model_input_result["ok"]:
        warnings.append("audio_normalization_failed")

    speech_result = run_silence_detect(
        str(audio_model_input_path),
        duration_sec=duration_sec,
        ffmpeg_bin=ffmpeg_bin,
    ) if model_input_result["ok"] else silence_detect_result(
        False,
        [],
        [],
        duration_sec,
        model_input_result["error"] or "normalized audio input missing",
    )
    record["speechActivity"].update(speech_result)
    if not speech_result["ok"]:
        warnings.append("speech_activity_detection_failed")

    try:
        model_result = run_audio_reference_models(
            audio_path=audio_model_input_path,
            speech_candidates=speech_result["speechCandidates"],
            source_name=probe_record["sourceIdentity"]["sourcePath"],
            settings=settings,
            mode=audio_model_mode,
        )
    finally:
        cleanup_result = remove_temporary_audio(audio_model_input_path)
        record["audioModelInput"].update(cleanup_result)
    record["audioModels"] = model_result
    record["diarization"] = model_result["diarization"]
    record["acousticUnits"] = model_result["acousticUnits"]
    record["text"] = model_result["text"]
    warnings.extend(model_result.get("warnings", []))

    record["ok"] = extract_result["ok"] and model_input_result["ok"] and speech_result["ok"] and model_result["ok"]
    return write_audio_analysis(record, audio_analysis_path)


def ffmpeg_timeout_seconds(duration_sec: float | None) -> int:
    if not isinstance(duration_sec, (int, float)) or duration_sec <= 0:
        return MIN_FFMPEG_TIMEOUT_SEC
    scaled = int(duration_sec / FFMPEG_TIMEOUT_DURATION_DIVISOR) + FFMPEG_TIMEOUT_MARGIN_SEC
    return min(MAX_FFMPEG_TIMEOUT_SEC, max(MIN_FFMPEG_TIMEOUT_SEC, scaled))


def remove_partial_output(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def run_audio_extract(source_path: str, output_path: Path, ffmpeg_bin: str, duration_sec: float | None) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    timeout_sec = ffmpeg_timeout_seconds(duration_sec)
    command = command_prefix(ffmpeg_bin) + [
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source_path,
        "-vn",
        "-map",
        "0:a:0",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "4",
        "-y",
        str(output_path),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_sec)
    except FileNotFoundError as exc:
        return {"ok": False, "command": command, "timeoutSec": timeout_sec, "error": str(exc)}
    except subprocess.TimeoutExpired:
        remove_partial_output(output_path)
        return {"ok": False, "command": command, "timeoutSec": timeout_sec, "error": "ffmpeg audio extraction timed out"}
    if completed.returncode != 0:
        return {
            "ok": False,
            "command": command,
            "timeoutSec": timeout_sec,
            "error": completed.stderr.strip() or completed.stdout.strip() or f"ffmpeg exited with {completed.returncode}",
        }
    return {
        "ok": output_path.exists(),
        "command": command,
        "timeoutSec": timeout_sec,
        "error": None if output_path.exists() else "audio artifact missing",
    }


def run_normalized_audio_extract(
    source_path: str,
    output_path: Path,
    ffmpeg_bin: str,
    duration_sec: float | None,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    timeout_sec = ffmpeg_timeout_seconds(duration_sec)
    command = command_prefix(ffmpeg_bin) + [
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source_path,
        "-vn",
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-sample_fmt",
        "s16",
        "-f",
        "wav",
        "-y",
        str(output_path),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_sec)
    except FileNotFoundError as exc:
        return {"ok": False, "command": command, "timeoutSec": timeout_sec, "error": str(exc)}
    except subprocess.TimeoutExpired:
        remove_partial_output(output_path)
        return {"ok": False, "command": command, "timeoutSec": timeout_sec, "error": "ffmpeg audio normalization timed out"}
    if completed.returncode != 0:
        return {
            "ok": False,
            "command": command,
            "timeoutSec": timeout_sec,
            "error": completed.stderr.strip() or completed.stdout.strip() or f"ffmpeg exited with {completed.returncode}",
        }
    return {
        "ok": output_path.exists(),
        "command": command,
        "timeoutSec": timeout_sec,
        "error": None if output_path.exists() else "normalized audio missing",
    }


def remove_temporary_audio(path: Path) -> dict[str, Any]:
    removed = False
    error = None
    if path.exists():
        try:
            path.unlink()
            removed = True
        except Exception as exc:
            error = f"temporary_audio_cleanup_failed:{exc}"
    try:
        path.parent.rmdir()
    except OSError:
        pass
    return {
        "removedAfterProcessing": removed or not path.exists(),
        "cleanupError": error,
    }


def run_silence_detect(source_path: str, duration_sec: float | None, ffmpeg_bin: str) -> dict[str, Any]:
    timeout_sec = ffmpeg_timeout_seconds(duration_sec)
    command = command_prefix(ffmpeg_bin) + [
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        source_path,
        "-af",
        f"silencedetect=noise={SILENCE_NOISE}:d={SILENCE_DURATION_SEC:.2f}",
        "-f",
        "null",
        "-",
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_sec)
    except FileNotFoundError as exc:
        result = silence_detect_result(False, command, [], duration_sec, str(exc))
        result["timeoutSec"] = timeout_sec
        return result
    except subprocess.TimeoutExpired:
        result = silence_detect_result(False, command, [], duration_sec, "ffmpeg silencedetect timed out")
        result["timeoutSec"] = timeout_sec
        return result

    output = "\n".join(part for part in [completed.stderr, completed.stdout] if part)
    silences = parse_silences(output)
    ok = completed.returncode == 0
    error = None if ok else output.strip() or f"ffmpeg exited with {completed.returncode}"
    result = silence_detect_result(ok, command, silences, duration_sec, error)
    result["timeoutSec"] = timeout_sec
    return result


def silence_detect_result(
    ok: bool,
    command: list[str],
    silences: list[dict[str, float]],
    duration_sec: float | None,
    error: str | None,
) -> dict[str, Any]:
    speech_candidates = speech_candidates_from_silences(duration_sec, silences)
    return {
        "ok": ok,
        "command": command,
        "silences": silences,
        "speechCandidates": speech_candidates,
        "counts": {
            "silences": len(silences),
            "speechCandidates": len(speech_candidates),
        },
        "error": error,
    }


def parse_silences(output: str) -> list[dict[str, float]]:
    silences: list[dict[str, float]] = []
    pending_start: float | None = None
    for line in output.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue
        end_match = re.search(r"silence_end:\s*([0-9.]+).*silence_duration:\s*([0-9.]+)", line)
        if end_match and pending_start is not None:
            end = float(end_match.group(1))
            duration = float(end_match.group(2))
            silences.append(
                {
                    "startSec": round(pending_start, 3),
                    "endSec": round(end, 3),
                    "durationSec": round(duration, 3),
                }
            )
            pending_start = None
    return silences


def speech_candidates_from_silences(
    duration_sec: float | None,
    silences: list[dict[str, float]],
) -> list[dict[str, float]]:
    if duration_sec is None or duration_sec <= 0:
        return []

    candidates: list[dict[str, float]] = []
    cursor = 0.0
    for silence in sorted(silences, key=lambda item: item["startSec"]):
        start = max(0.0, float(silence["startSec"]))
        end = max(start, float(silence["endSec"]))
        if start > cursor:
            candidates.append(candidate(cursor, start))
        cursor = max(cursor, end)
    if cursor < duration_sec:
        candidates.append(candidate(cursor, duration_sec))
    return [entry for entry in candidates if entry["durationSec"] > 0]


def candidate(start: float, end: float) -> dict[str, float]:
    return {
        "startSec": round(start, 3),
        "endSec": round(end, 3),
        "durationSec": round(max(0.0, end - start), 3),
    }


def write_audio_analysis(record: dict[str, Any], path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def model_turn_count(payload: dict[str, Any]) -> int:
    return int(payload.get("turn_count") or 0)
