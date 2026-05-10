from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import importlib.util
import os
from pathlib import Path
from typing import Any

from .probe import utc_now_iso
from .settings import load_huggingface_token


AUDIO_MODEL_RESULT_SCHEMA_VERSION = "timeline_for_video.audio_model_result.v1"
AUDIO_MODEL_MODES = ("auto", "off", "required")
DIARIZATION_BACKEND = "pyannote.audio"
DIARIZATION_MODEL_ID = "pyannote/speaker-diarization-community-1"
ACOUSTIC_UNIT_BACKEND = "zipa-large-crctc-300k-onnx-v1"
ACOUSTIC_UNIT_MODEL_ID = "anyspeech/zipa-large-crctc-300k"
ACOUSTIC_UNIT_TYPE = "phone_like"
ACOUSTIC_MODEL_FILE = "model.onnx"
ACOUSTIC_TOKENS_FILE = "tokens.txt"
MAX_ACOUSTIC_CHUNK_SECONDS = 30.0
MIN_ACOUSTIC_SPAN_SECONDS = 1.0
DIARIZATION_ACTIVITY_PADDING_SEC = 1.0
DIARIZATION_ACTIVITY_MERGE_GAP_SEC = 2.0
TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD = "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"
WORKER_FLAVOR_ENV = "TIMELINE_FOR_VIDEO_WORKER_FLAVOR"
NONFATAL_DIARIZATION_STATUSES = {"ok", "no_speaker_turns"}
NONFATAL_ACOUSTIC_UNIT_STATUSES = {"ok", "no_turns"}


def normalize_audio_model_mode(mode: str | None) -> str:
    normalized = str(mode or "required").strip().casefold()
    if normalized not in AUDIO_MODEL_MODES:
        raise ValueError(f"audio model mode must be one of: {', '.join(AUDIO_MODEL_MODES)}")
    return normalized


def normalize_compute_mode(mode: str | None) -> str:
    normalized = str(mode or "gpu").strip().casefold()
    if normalized not in {"cpu", "gpu"}:
        raise ValueError("compute mode must be one of: cpu, gpu")
    return normalized


def audio_model_runtime_status(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    compute_mode = normalize_compute_mode(settings.get("computeMode") if settings else None)
    modules = {
        "pyannote.audio": module_available("pyannote.audio"),
        "torch": module_available("torch"),
        "torchaudio": module_available("torchaudio"),
        "onnxruntime": module_available("onnxruntime"),
        "huggingface_hub": module_available("huggingface_hub"),
        "lhotse": module_available("lhotse"),
        "numpy": module_available("numpy"),
    }
    token_ready = bool(load_huggingface_token(settings))
    compute = compute_runtime_status(compute_mode, modules)
    ready = token_ready and all(modules.values()) and compute["ready"]
    return {
        "ready": ready,
        "computeMode": compute_mode,
        "compute": compute,
        "tokenConfigured": token_ready,
        "modules": modules,
        "diarization": {
            "backend": DIARIZATION_BACKEND,
            "modelId": DIARIZATION_MODEL_ID,
            "ready": token_ready and modules["pyannote.audio"] and modules["torch"] and modules["torchaudio"] and compute["ready"],
        },
        "acousticUnits": {
            "backend": ACOUSTIC_UNIT_BACKEND,
            "modelId": ACOUSTIC_UNIT_MODEL_ID,
            "unitType": ACOUSTIC_UNIT_TYPE,
            "ready": compute["ready"] and all(
                modules[name]
                for name in ["torch", "torchaudio", "onnxruntime", "huggingface_hub", "lhotse", "numpy"]
            ),
        },
    }


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def compute_runtime_status(compute_mode: str, modules: dict[str, bool]) -> dict[str, Any]:
    worker_flavor = str(os.getenv(WORKER_FLAVOR_ENV) or "cpu").strip().casefold()
    if compute_mode == "cpu":
        return {
            "ready": True,
            "mode": "cpu",
            "workerFlavor": worker_flavor,
            "torchCudaAvailable": None,
            "onnxProviders": [],
            "warnings": [],
        }

    warnings: list[str] = []
    if worker_flavor != "gpu":
        warnings.append("computeMode gpu requires the GPU worker flavor.")

    torch_cuda_available = False
    if modules.get("torch"):
        try:
            import torch

            torch_cuda_available = bool(getattr(torch.cuda, "is_available", lambda: False)())
        except Exception as exc:
            warnings.append(f"torch_cuda_check_failed:{exc}")
    else:
        warnings.append("torch is not available.")

    if not torch_cuda_available:
        warnings.append("CUDA is not available to torch.")

    providers: list[str] = []
    if modules.get("onnxruntime"):
        try:
            import onnxruntime as ort

            providers = [str(provider) for provider in ort.get_available_providers()]
        except Exception as exc:
            warnings.append(f"onnxruntime_provider_check_failed:{exc}")
    else:
        warnings.append("onnxruntime is not available.")

    if "CUDAExecutionProvider" not in providers:
        warnings.append("CUDAExecutionProvider is not available to ONNX Runtime.")

    return {
        "ready": not warnings,
        "mode": "gpu",
        "workerFlavor": worker_flavor,
        "torchCudaAvailable": torch_cuda_available,
        "onnxProviders": providers,
        "warnings": warnings,
    }


def run_audio_reference_models(
    *,
    audio_path: Path,
    speech_candidates: list[dict[str, float]],
    source_name: str,
    settings: dict[str, Any],
    mode: str | None = None,
) -> dict[str, Any]:
    model_mode = normalize_audio_model_mode(mode)
    compute_mode = normalize_compute_mode(settings.get("computeMode"))
    generated_at = utc_now_iso()
    runtime = audio_model_runtime_status(settings)

    result = {
        "schemaVersion": AUDIO_MODEL_RESULT_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "ok": True,
        "mode": model_mode,
        "computeMode": compute_mode,
        "runtime": runtime,
        "diarization": empty_diarization("not_run"),
        "acousticUnits": empty_acoustic_units("not_run"),
        "text": {
            "mode": "audio_reference_units",
            "readableText": "",
            "segments": [],
            "warnings": [
                "TimelineForAudio stores phone-like acoustic units, not readable prose transcripts."
            ],
        },
        "warnings": [],
    }

    if model_mode == "off":
        result["diarization"] = empty_diarization("disabled")
        result["acousticUnits"] = empty_acoustic_units("disabled")
        result["warnings"].append("audio_model_mode_off")
        return result

    if not audio_path.exists():
        result["ok"] = False
        result["diarization"] = empty_diarization("audio_missing")
        result["acousticUnits"] = empty_acoustic_units("audio_missing")
        result["warnings"].append(f"audio_model_input_missing:{audio_path}")
        return result

    token = load_huggingface_token(settings)
    if not token:
        result["ok"] = model_mode != "required"
        result["diarization"] = empty_diarization("not_configured")
        result["acousticUnits"] = empty_acoustic_units("not_configured")
        result["warnings"].append("hugging_face_token_missing")
        return result

    missing = [name for name, available in runtime["modules"].items() if not available]
    if missing:
        result["ok"] = model_mode != "required"
        result["diarization"] = empty_diarization("dependencies_missing")
        result["acousticUnits"] = empty_acoustic_units("dependencies_missing")
        result["warnings"].append("missing_audio_model_dependencies:" + ",".join(sorted(missing)))
        return result

    if not runtime["compute"]["ready"]:
        result["ok"] = False
        result["diarization"] = empty_diarization("compute_runtime_unavailable")
        result["acousticUnits"] = empty_acoustic_units("compute_runtime_unavailable")
        result["warnings"].extend(f"gpu_runtime_unavailable:{warning}" for warning in runtime["compute"]["warnings"])
        return result

    try:
        diarization = run_diarization(audio_path, token, compute_mode, source_name, speech_candidates)
        result["diarization"] = diarization
    except Exception as exc:
        result["ok"] = False
        result["diarization"] = failed_diarization(str(exc))
        result["acousticUnits"] = empty_acoustic_units("not_run")
        result["warnings"].append(f"diarization_failed:{exc}")
        return result

    try:
        acoustic = run_acoustic_units(audio_path, speech_candidates, compute_mode, diarization.get("turns", []))
        result["acousticUnits"] = acoustic
        result["text"]["segments"] = acoustic.get("turns", [])
    except Exception as exc:
        result["ok"] = False
        result["acousticUnits"] = failed_acoustic_units(str(exc))
        result["warnings"].append(f"acoustic_unit_extraction_failed:{exc}")
        return result

    if (
        result["diarization"].get("status") not in NONFATAL_DIARIZATION_STATUSES
        or result["acousticUnits"].get("status") not in NONFATAL_ACOUSTIC_UNIT_STATUSES
    ):
        result["ok"] = model_mode != "required"
    return result


def empty_diarization(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "backend": DIARIZATION_BACKEND,
        "model_id": DIARIZATION_MODEL_ID,
        "turns": [],
        "turn_count": 0,
        "warning_count": 0,
        "warnings": [],
        "error": None,
    }


def failed_diarization(error: str) -> dict[str, Any]:
    payload = empty_diarization("failed")
    payload["error"] = error
    payload["warnings"] = [error]
    payload["warning_count"] = 1
    return payload


def empty_acoustic_units(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "backend": ACOUSTIC_UNIT_BACKEND,
        "model_id": ACOUSTIC_UNIT_MODEL_ID,
        "unit_type": ACOUSTIC_UNIT_TYPE,
        "execution_provider": None,
        "available_execution_providers": [],
        "turns": [],
        "turn_count": 0,
        "warning_count": 0,
        "warnings": [],
        "error": None,
    }


def failed_acoustic_units(error: str) -> dict[str, Any]:
    payload = empty_acoustic_units("failed")
    payload["error"] = error
    payload["warnings"] = [error]
    payload["warning_count"] = 1
    return payload


@contextmanager
def torch_checkpoint_loading_without_weights_only() -> Any:
    previous = os.environ.get(TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD)
    os.environ[TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD, None)
        else:
            os.environ[TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD] = previous


@lru_cache(maxsize=2)
def load_diarization_pipeline(token: str, compute_mode: str) -> Any:
    from pyannote.audio import Pipeline

    with torch_checkpoint_loading_without_weights_only():
        pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL_ID, token=token)
    if compute_mode == "gpu":
        import torch

        if getattr(torch.cuda, "is_available", lambda: False)() and hasattr(pipeline, "to"):
            pipeline.to(torch.device("cuda"))
    return pipeline


def run_diarization(
    audio_path: Path,
    token: str,
    compute_mode: str,
    source_name: str,
    speech_candidates: list[dict[str, float]] | None = None,
) -> dict[str, Any]:
    pipeline = load_diarization_pipeline(token, compute_mode)
    scope = {
        "mode": "full_audio" if speech_candidates is None else "speech_candidates",
        "paddingSec": DIARIZATION_ACTIVITY_PADDING_SEC if speech_candidates is not None else None,
        "mergeGapSec": DIARIZATION_ACTIVITY_MERGE_GAP_SEC if speech_candidates is not None else None,
        "spans": 1,
        "activeSec": None,
    }
    if speech_candidates is None:
        audio_input = load_diarization_audio_input(audio_path)
        output = pipeline(audio_input)
        turns = diarization_turns(output)
    else:
        spans = diarization_activity_spans(speech_candidates)
        scope["spans"] = len(spans)
        scope["activeSec"] = round(sum(end - start for start, end in spans), 3)
        if not spans:
            return {
                "status": "no_speaker_turns",
                "source_name": source_name,
                "backend": DIARIZATION_BACKEND,
                "model_id": DIARIZATION_MODEL_ID,
                "scope": scope,
                "turns": [],
                "turn_count": 0,
                "warning_count": 1,
                "warnings": ["Speaker diarization skipped because no speech candidates were found."],
                "error": None,
            }
        turns = []
        for start, end in spans:
            audio_input = load_diarization_audio_input(audio_path, start_sec=start, end_sec=end)
            output = pipeline(audio_input)
            turns.extend(diarization_turns(output, offset_sec=start))
    status = "ok" if turns else "no_speaker_turns"
    warnings = [] if turns else ["Speaker diarization completed, but no speaker turns were found."]
    return {
        "status": status,
        "source_name": source_name,
        "backend": DIARIZATION_BACKEND,
        "model_id": DIARIZATION_MODEL_ID,
        "scope": scope,
        "turns": turns,
        "turn_count": len(turns),
        "warning_count": len(warnings),
        "warnings": warnings,
        "error": None,
    }


def load_diarization_audio_input(
    audio_path: Path,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> dict[str, Any]:
    import torchaudio

    if start_sec is None or end_sec is None:
        waveform, sample_rate = torchaudio.load(str(audio_path))
    else:
        metadata = torchaudio.info(str(audio_path))
        source_sample_rate = int(getattr(metadata, "sample_rate", 0) or 16000)
        frame_offset = max(0, int(round(start_sec * source_sample_rate)))
        num_frames = max(1, int(round((end_sec - start_sec) * source_sample_rate)))
        waveform, sample_rate = torchaudio.load(
            str(audio_path),
            frame_offset=frame_offset,
            num_frames=num_frames,
        )
    if hasattr(waveform, "dim") and callable(getattr(waveform, "dim")) and waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)
    return {
        "waveform": waveform,
        "sample_rate": int(sample_rate),
    }


def diarization_turns(output: Any, offset_sec: float = 0.0) -> list[dict[str, Any]]:
    annotation = getattr(output, "exclusive_speaker_diarization", None)
    if annotation is None or not hasattr(annotation, "itertracks"):
        annotation = getattr(output, "speaker_diarization", None)
    if annotation is None or not hasattr(annotation, "itertracks"):
        annotation = output
    turns: list[dict[str, Any]] = []
    for segment, _, speaker in annotation.itertracks(yield_label=True):
        turns.append(
            {
                "start": round(float(segment.start) + offset_sec, 3),
                "end": round(float(segment.end) + offset_sec, 3),
                "speaker": str(speaker),
            }
        )
    return turns


def diarization_activity_spans(speech_candidates: list[dict[str, float]]) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    for candidate in speech_candidates:
        try:
            start = max(0.0, float(candidate.get("startSec", 0.0)) - DIARIZATION_ACTIVITY_PADDING_SEC)
            end = float(candidate.get("endSec", start)) + DIARIZATION_ACTIVITY_PADDING_SEC
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        spans.append((start, end))
    spans.sort(key=lambda span: span[0])
    merged: list[tuple[float, float]] = []
    for start, end in spans:
        if not merged or start - merged[-1][1] > DIARIZATION_ACTIVITY_MERGE_GAP_SEC:
            merged.append((start, end))
        else:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
    return [(round(start, 3), round(end, 3)) for start, end in merged]


def run_acoustic_units(
    audio_path: Path,
    speech_candidates: list[dict[str, float]],
    compute_mode: str,
    speaker_turns: list[dict[str, Any]],
) -> dict[str, Any]:
    import numpy as np
    import onnxruntime as ort
    import torchaudio
    from huggingface_hub import hf_hub_download
    from lhotse.features.kaldi.extractors import Fbank, FbankConfig

    model_path = Path(hf_hub_download(repo_id=ACOUSTIC_UNIT_MODEL_ID, filename=ACOUSTIC_MODEL_FILE))
    token_path = Path(hf_hub_download(repo_id=ACOUSTIC_UNIT_MODEL_ID, filename=ACOUSTIC_TOKENS_FILE))
    providers = onnx_providers(ort, compute_mode)
    session = ort.InferenceSession(str(model_path), providers=providers or None)
    vocab = load_token_vocab(token_path)
    extractor = Fbank(FbankConfig(num_filters=80, dither=0.0, snip_edges=False))
    source_sample_rate, duration_seconds = audio_info(torchaudio, audio_path)
    spans = acoustic_unit_spans(speech_candidates, duration_seconds)
    turns: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, span in enumerate(spans, start=1):
        start = float(span.get("startSec", 0.0) or 0.0)
        end = float(span.get("endSec", start) or start)
        if end <= start:
            continue
        token_parts: list[str] = []
        confidences: list[float] = []
        for chunk_start, chunk_end in iter_chunks(start, end, MAX_ACOUSTIC_CHUNK_SECONDS):
            if chunk_end - chunk_start < MIN_ACOUSTIC_SPAN_SECONDS:
                warnings.append(f"acoustic_chunk_too_short:{chunk_start:.3f}-{chunk_end:.3f}")
                continue
            try:
                chunk_waveform, chunk_sample_rate = load_audio_chunk(
                    torchaudio_module=torchaudio,
                    audio_path=audio_path,
                    source_sample_rate=source_sample_rate,
                    start=chunk_start,
                    end=chunk_end,
                )
                text, confidence = decode_acoustic_waveform(
                    waveform=chunk_waveform,
                    sample_rate=chunk_sample_rate,
                    extractor=extractor,
                    session=session,
                    vocab=vocab,
                    numpy_module=np,
                )
            except Exception as exc:
                warnings.append(f"acoustic_chunk_failed:{chunk_start:.3f}-{chunk_end:.3f}:{exc}")
                continue
            if text:
                token_parts.append(text)
            if confidence is not None:
                confidences.append(confidence)
        phone_tokens = " ".join(" ".join(token_parts).split())
        if not phone_tokens:
            continue
        turns.append(
            {
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "speaker": speaker_for_interval(start, end, speaker_turns),
                "phone_tokens": phone_tokens,
                "unit_type": ACOUSTIC_UNIT_TYPE,
                "confidence": round(sum(confidences) / len(confidences), 6) if confidences else None,
                "index": index,
            }
        )

    status = "ok" if turns else "no_turns"
    if not turns:
        warnings.append("Acoustic unit extraction produced no turns.")
    return {
        "status": status,
        "backend": ACOUSTIC_UNIT_BACKEND,
        "model_id": ACOUSTIC_UNIT_MODEL_ID,
        "unit_type": ACOUSTIC_UNIT_TYPE,
        "execution_provider": str(session.get_providers()[0]) if session.get_providers() else None,
        "available_execution_providers": [str(provider) for provider in ort.get_available_providers()],
        "turns": turns,
        "turn_count": len(turns),
        "warning_count": len(warnings),
        "warnings": warnings,
        "error": None,
    }


def acoustic_unit_spans(speech_candidates: list[dict[str, float]], duration_seconds: float) -> list[dict[str, float]]:
    if not speech_candidates:
        return [{"startSec": 0.0, "endSec": duration_seconds}]
    spans = []
    for start, end in diarization_activity_spans(speech_candidates):
        bounded_start = max(0.0, min(duration_seconds, start))
        bounded_end = max(0.0, min(duration_seconds, end))
        if bounded_end - bounded_start < MIN_ACOUSTIC_SPAN_SECONDS:
            continue
        spans.append({"startSec": round(bounded_start, 3), "endSec": round(bounded_end, 3)})
    return spans


def audio_info(torchaudio_module: Any, audio_path: Path) -> tuple[int, float]:
    metadata = torchaudio_module.info(str(audio_path))
    sample_rate = int(getattr(metadata, "sample_rate", 0) or 0)
    num_frames = int(getattr(metadata, "num_frames", 0) or 0)
    if sample_rate <= 0:
        waveform, sample_rate = torchaudio_module.load(str(audio_path))
        num_frames = int(waveform.shape[-1])
    duration_seconds = num_frames / max(1, sample_rate)
    return sample_rate, duration_seconds


def load_audio_chunk(
    *,
    torchaudio_module: Any,
    audio_path: Path,
    source_sample_rate: int,
    start: float,
    end: float,
) -> tuple[Any, int]:
    frame_offset = max(0, int(round(start * source_sample_rate)))
    num_frames = max(1, int(round((end - start) * source_sample_rate)))
    waveform, sample_rate = torchaudio_module.load(
        str(audio_path),
        frame_offset=frame_offset,
        num_frames=num_frames,
    )
    if hasattr(waveform, "dim") and waveform.dim() > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if int(sample_rate) != 16000:
        waveform = torchaudio_module.functional.resample(waveform, int(sample_rate), 16000)
        sample_rate = 16000
    return waveform, int(sample_rate)


def onnx_providers(ort_module: Any, compute_mode: str) -> list[str]:
    available = [str(provider) for provider in ort_module.get_available_providers()]
    if compute_mode == "gpu":
        if "CUDAExecutionProvider" not in available:
            raise RuntimeError("GPU compute mode requested, but CUDAExecutionProvider is not available.")
        return ["CUDAExecutionProvider", "CPUExecutionProvider"] if "CPUExecutionProvider" in available else ["CUDAExecutionProvider"]
    return ["CPUExecutionProvider"] if "CPUExecutionProvider" in available else available


def load_token_vocab(path: Path) -> dict[int, str]:
    vocab: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        try:
            index = int(parts[1]) if len(parts) > 1 else len(vocab)
        except ValueError:
            index = len(vocab)
        vocab[index] = parts[0]
    return vocab


def iter_chunks(start: float, end: float, max_seconds: float) -> list[tuple[float, float]]:
    chunks: list[tuple[float, float]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(end, cursor + max_seconds)
        if chunk_end <= cursor:
            break
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks


def decode_acoustic_chunk(
    *,
    waveform: Any,
    sample_rate: int,
    start: float,
    end: float,
    extractor: Any,
    session: Any,
    vocab: dict[int, str],
    numpy_module: Any,
) -> tuple[str, float | None]:
    start_sample = max(0, int(round(start * sample_rate)))
    end_sample = max(start_sample, int(round(end * sample_rate)))
    chunk = waveform[..., start_sample:end_sample]
    return decode_acoustic_waveform(
        waveform=chunk,
        sample_rate=sample_rate,
        extractor=extractor,
        session=session,
        vocab=vocab,
        numpy_module=numpy_module,
    )


def decode_acoustic_waveform(
    *,
    waveform: Any,
    sample_rate: int,
    extractor: Any,
    session: Any,
    vocab: dict[int, str],
    numpy_module: Any,
) -> tuple[str, float | None]:
    chunk = waveform
    if hasattr(chunk, "dim") and chunk.dim() > 1:
        chunk = chunk.squeeze(0)
    features = extractor.extract_batch([chunk.float()], sampling_rate=sample_rate)
    feature = features[0].unsqueeze(0)
    feature_lens = numpy_module.array([feature.shape[1]], dtype=numpy_module.int64)
    outputs = session.run(None, {"x": feature.numpy(), "x_lens": feature_lens})
    log_probs = outputs[0][0]
    if len(log_probs.shape) == 3:
        log_probs = log_probs[0]
    predictions = numpy_module.argmax(log_probs, axis=-1)
    decoded: list[str] = []
    previous = -1
    blank_id = 0
    for value in predictions:
        index = int(value)
        if index != blank_id and index != previous:
            token = vocab.get(index, "")
            if token:
                decoded.append(token)
        previous = index
    confidence = None
    try:
        confidence = float(numpy_module.mean(numpy_module.max(log_probs, axis=-1)))
    except Exception:
        confidence = None
    return " ".join(" ".join(decoded).split()), confidence


def speaker_for_interval(start: float, end: float, speaker_turns: list[dict[str, Any]]) -> str:
    midpoint = start + ((end - start) / 2.0)
    best_speaker = "SPEAKER_00"
    best_overlap = 0.0
    for turn in speaker_turns:
        turn_start = float(turn.get("startSec", turn.get("start", 0.0)) or 0.0)
        turn_end = float(turn.get("endSec", turn.get("end", turn_start)) or turn_start)
        overlap = max(0.0, min(end, turn_end) - max(start, turn_start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = str(turn.get("speaker") or best_speaker)
    if best_overlap > 0:
        return best_speaker
    for turn in speaker_turns:
        turn_start = float(turn.get("startSec", turn.get("start", 0.0)) or 0.0)
        turn_end = float(turn.get("endSec", turn.get("end", turn_start)) or turn_start)
        if turn_start <= midpoint <= turn_end:
            return str(turn.get("speaker") or best_speaker)
    return best_speaker
