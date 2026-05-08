from __future__ import annotations

import importlib.util
from typing import Any

from . import __version__
from .audio_analysis import (
    SILENCE_DETECT_BACKEND,
    SILENCE_DETECT_MODEL_ID,
)
from .audio_models import (
    ACOUSTIC_UNIT_BACKEND,
    ACOUSTIC_UNIT_MODEL_ID,
    ACOUSTIC_UNIT_TYPE,
    DIARIZATION_BACKEND,
    DIARIZATION_MODEL_ID,
    audio_model_runtime_status,
    normalize_audio_model_mode,
)
from .frame_ocr import OCR_MODEL_ID, ocr_runtime_status
from .probe import ffprobe_version, utc_now_iso
from .sampling import ffmpeg_version
from .settings import PRODUCT_NAME


MODEL_INVENTORY_SCHEMA_VERSION = "timeline_for_video.model_inventory.v1"


def build_model_inventory(
    ffprobe_bin: str = "ffprobe",
    ffmpeg_bin: str = "ffmpeg",
    ocr_mode: str = "auto",
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = utc_now_iso()
    ffprobe_status = ffprobe_version(ffprobe_bin)
    ffmpeg_status = ffmpeg_version(ffmpeg_bin)
    ocr_status = ocr_runtime_status(ocr_mode)
    visual_status = visual_feature_runtime_status()
    audio_model_status = audio_model_runtime_status(settings)
    audio_model_mode = normalize_audio_model_mode(settings.get("audioModelMode") if settings else None)
    audio_model_required = audio_model_mode == "required"
    components = [
        local_component(
            component_id="ffprobe_metadata",
            display_name="ffprobe metadata",
            role="Read source video metadata.",
            ready=ffprobe_status["ok"],
            backend="ffprobe",
            runtime=ffprobe_status,
        ),
        local_component(
            component_id="bounded_frame_sampling",
            display_name="bounded frame sampling",
            role="Extract bounded JPEG frame evidence from source videos.",
            ready=ffmpeg_status["ok"],
            backend="ffmpeg",
            runtime=ffmpeg_status,
        ),
        local_component(
            component_id="frame_ocr",
            display_name="frame OCR",
            role="Run local OCR over generated frame artifacts.",
            ready=ocr_status["ok"],
            backend="pytesseract",
            model_id=OCR_MODEL_ID,
            runtime=ocr_status,
            reference_product="TimelineForImage",
        ),
        local_component(
            component_id="frame_visual_features",
            display_name="frame visual features",
            role="Measure brightness, contrast, dominant colors, and a 3x3 color grid over generated frame artifacts.",
            ready=visual_status["ok"],
            backend="Pillow",
            runtime=visual_status,
            reference_product="TimelineForImage",
        ),
        local_component(
            component_id="audio_derivative",
            display_name="audio derivative",
            role="Create a local MP3 evidence artifact under outputRoot.",
            ready=ffmpeg_status["ok"],
            backend="ffmpeg",
            runtime=ffmpeg_status,
        ),
        local_component(
            component_id="speech_candidate_detection",
            display_name="speech candidate detection",
            role="Detect non-silent audio ranges for timeline evidence.",
            ready=ffmpeg_status["ok"],
            backend=SILENCE_DETECT_BACKEND,
            model_id=SILENCE_DETECT_MODEL_ID,
            runtime=ffmpeg_status,
            reference_product="TimelineForAudio",
        ),
        audio_model_component(
            component_id="speaker_diarization",
            display_name="speaker diarization",
            role="Run TimelineForAudio-compatible speaker diarization over generated audio.",
            backend=DIARIZATION_BACKEND,
            model_id=DIARIZATION_MODEL_ID,
            ready=audio_model_status["diarization"]["ready"],
            runtime=audio_model_status,
            required=audio_model_required,
            requires_access_approval=True,
        ),
        audio_model_component(
            component_id="acoustic_units",
            display_name="acoustic units",
            role="Run TimelineForAudio-compatible phone-like acoustic-unit extraction over generated audio.",
            backend=ACOUSTIC_UNIT_BACKEND,
            model_id=ACOUSTIC_UNIT_MODEL_ID,
            unit_type=ACOUSTIC_UNIT_TYPE,
            ready=audio_model_status["acousticUnits"]["ready"],
            runtime=audio_model_status,
            required=audio_model_required,
        ),
    ]
    required_components = [component for component in components if component["execution"]["required"]]
    audio_model_components = [component for component in components if component["execution"]["kind"] == "audio_model"]
    return {
        "schemaVersion": MODEL_INVENTORY_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": __version__,
        "generatedAt": generated_at,
        "audioModelMode": audio_model_mode,
        "ok": all(component["runtime"]["ready"] for component in required_components),
        "sourceVideoSafety": {
            "sourceVideoModified": False,
            "sourceVideosIncludedInZip": False,
            "generatedAudioIncludedInZip": False,
            "externalAnalysisApiUsed": False,
        },
        "counts": {
            "components": len(components),
            "requiredComponents": len(required_components),
            "readyRequiredComponents": sum(1 for component in required_components if component["runtime"]["ready"]),
            "audioModelComponents": len(audio_model_components),
            "readyAudioModelComponents": sum(1 for component in audio_model_components if component["runtime"]["ready"]),
        },
        "components": components,
    }


def visual_feature_runtime_status() -> dict[str, Any]:
    ready = importlib.util.find_spec("PIL") is not None
    return {
        "ok": ready,
        "module": "PIL",
        "message": "Pillow is ready." if ready else "Pillow is not available.",
    }


def local_component(
    *,
    component_id: str,
    display_name: str,
    role: str,
    ready: bool,
    backend: str,
    runtime: dict[str, Any],
    model_id: str | None = None,
    reference_product: str | None = None,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "displayName": display_name,
        "role": role,
        "backend": backend,
        "modelId": model_id,
        "referenceProduct": reference_product,
        "execution": {
            "kind": "local",
            "required": True,
            "implementedInVideoWorker": True,
            "sourceSharing": False,
        },
        "runtime": {
            "ready": bool(ready),
            "details": runtime,
        },
    }


def audio_model_component(
    *,
    component_id: str,
    display_name: str,
    role: str,
    backend: str,
    model_id: str,
    ready: bool,
    runtime: dict[str, Any],
    required: bool,
    requires_access_approval: bool = False,
    unit_type: str | None = None,
) -> dict[str, Any]:
    details = dict(runtime)
    details["audioModelsReady"] = bool(details.pop("ready", False))
    details["componentReady"] = bool(ready)
    details["requiresAccessApproval"] = requires_access_approval
    return {
        "id": component_id,
        "displayName": display_name,
        "role": role,
        "backend": backend,
        "modelId": model_id,
        "unitType": unit_type,
        "referenceProduct": "TimelineForAudio",
        "execution": {
            "kind": "audio_model",
            "required": required,
            "implementedInVideoWorker": True,
            "sourceSharing": False,
            "status": "required_by_current_settings" if required else "runs_when_dependencies_and_token_are_available",
        },
        "runtime": {
            "ready": bool(ready),
            "details": details,
        },
    }
