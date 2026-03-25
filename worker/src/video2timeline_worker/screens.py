from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ChangeDetectionConfig
from .ffmpeg_utils import extract_frame
from .fs_utils import ensure_dir
from .settings import load_settings


def candidate_timestamps(duration_seconds: float) -> list[float]:
    if duration_seconds <= 1.0:
        return [0.0]

    count = max(4, min(16, int(duration_seconds // 30) + 4))
    if duration_seconds <= 12:
        count = 3

    step = duration_seconds / max(count - 1, 1)
    safe_end = max(0.0, duration_seconds - 0.05)
    timestamps: list[float] = []
    for idx in range(count):
        raw_value = idx * step
        safe_value = round(min(safe_end, raw_value), 3)
        if timestamps and abs(timestamps[-1] - safe_value) < 0.001:
            continue
        timestamps.append(safe_value)

    return timestamps or [0.0]


def _load_ocr_components() -> tuple[Any | None, Any | None]:
    settings = load_settings()
    use_gpu = False
    try:
        import torch
        use_gpu = str(settings.get("computeMode") or "cpu").lower() == "gpu" and torch.cuda.is_available()
    except Exception:
        use_gpu = False

    try:
        import easyocr
    except Exception:
        easyocr = None

    try:
        from transformers import pipeline
    except Exception:
        pipeline = None

    reader = easyocr.Reader(["ja", "en"], gpu=use_gpu, verbose=False) if easyocr else None
    captioner = (
        pipeline(
            "image-to-text",
            model="florence-community/Florence-2-base",
            device=0 if use_gpu else -1,
        )
        if pipeline
        else None
    )
    return reader, captioner


def _ocr_lines(image_path: Path, reader: Any | None) -> list[str]:
    if reader is None:
        return []

    try:
        rows = reader.readtext(str(image_path), detail=1, paragraph=False)
    except Exception:
        return []

    lines: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue

        text = " ".join(str(row[1] or "").split())
        if len(text) < 2:
            continue

        lowered = text.lower()
        if lowered in seen:
            continue

        seen.add(lowered)
        lines.append(text)
        if len(lines) >= 6:
            break

    return lines


def _caption_text(image_path: Path, captioner: Any | None) -> str:
    if captioner is None:
        return ""

    try:
        result = captioner(str(image_path), max_new_tokens=80)
    except Exception:
        return ""

    if not result:
        return ""

    value = str(result[0].get("generated_text", "") or "")
    return " ".join(value.split())


def _summarize(caption: str, ocr_lines: list[str], classification: str) -> str:
    if caption:
        return caption[:280]
    if ocr_lines:
        return f"OCR detected text. Top lines: {' / '.join(ocr_lines[:3])}"
    if classification == "same":
        return "大きな画面変化はありません。"
    if classification == "minor_change":
        return "軽微な画面変化があります。"
    return "大きな画面変化があります。"


def extract_screens(
    *,
    video_path: Path,
    screen_dir: Path,
    duration_seconds: float,
    thresholds: ChangeDetectionConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from .change_detection import compare_images

    ensure_dir(screen_dir)
    timestamps = candidate_timestamps(duration_seconds)
    frame_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    reader, captioner = _load_ocr_components()

    previous_path: Path | None = None
    previous_timestamp: float | None = None
    for idx, timestamp in enumerate(timestamps, start=1):
        image_path = screen_dir / f"screenshot_{idx:02d}.jpg"
        extract_frame(video_path, image_path, timestamp)

        if previous_path is None:
            classification = "major_change"
            diff_row = {
                "index": idx,
                "timestamp": timestamp,
                "classification": classification,
                "previous_timestamp": None,
                "changed": True,
                "diff_summary": "Initial frame.",
            }
        else:
            comparison = compare_images(previous_path, image_path, thresholds)
            classification = comparison.classification
            diff_row = {
                "index": idx,
                "timestamp": timestamp,
                "classification": classification,
                "previous_timestamp": previous_timestamp,
                "changed": comparison.classification != "same",
                "diff_summary": (
                    f"classification={comparison.classification}, "
                    f"phash={comparison.phash_distance}, mean_diff={comparison.mean_diff}"
                ),
            }

        diff_rows.append(diff_row)

        include_note = idx == 1 or classification == "major_change"
        if include_note:
            ocr_lines = _ocr_lines(image_path, reader)
            caption = _caption_text(image_path, captioner)
            frame_rows.append(
                {
                    "index": idx,
                    "timestamp": timestamp,
                    "filename": image_path.name,
                    "summary": _summarize(caption, ocr_lines, classification),
                    "caption": caption,
                    "ocr_lines": ocr_lines,
                    "classification": classification,
                }
            )

        previous_path = image_path
        previous_timestamp = timestamp

    (screen_dir / "screenshots.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in frame_rows) + ("\n" if frame_rows else ""),
        encoding="utf-8",
    )
    (screen_dir / "screen_diff.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in diff_rows) + ("\n" if diff_rows else ""),
        encoding="utf-8",
    )
    return frame_rows, diff_rows
