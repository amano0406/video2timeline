from __future__ import annotations

from pathlib import Path
from typing import Any

from .fs_utils import write_text


def _timestamp_label(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def _choose_screen_note(notes: list[dict[str, Any]], timestamp: float) -> dict[str, Any] | None:
    candidate = None
    for note in notes:
        if float(note["timestamp"]) <= timestamp:
            candidate = note
        else:
            break
    return candidate


def render_timeline(
    *,
    output_path: Path,
    source_info: dict[str, Any],
    transcript_payload: dict[str, Any],
    screen_notes: list[dict[str, Any]],
    screen_diffs: list[dict[str, Any]],
) -> str:
    lines = [
        "# Video Timeline",
        "",
        f"- Source: `{source_info.get('original_path') or source_info.get('video_path')}`",
        f"- Media ID: `{source_info.get('media_id')}`",
        f"- Duration: `{source_info.get('duration_seconds', 0):.3f}s`",
        "",
    ]

    segments = transcript_payload.get("segments", []) or []
    last_screen_index = None
    if segments:
        for segment in segments:
            start = float(segment.get("original_start", segment.get("start", 0.0)) or 0.0)
            end = float(segment.get("original_end", segment.get("end", start)) or start)
            note = _choose_screen_note(screen_notes, start)
            diff = None
            if note:
                for row in screen_diffs:
                    if int(row["index"]) == int(note["index"]):
                        diff = row
                        break

            lines.extend(
                [
                    f"## {_timestamp_label(start)} - {_timestamp_label(end)}",
                    "Speech:",
                    f"{segment.get('speaker', 'SPEAKER_00')}: {segment.get('text', '')}",
                    "",
                ]
            )
            if note and note["index"] != last_screen_index:
                lines.extend(
                    [
                        "Screen:",
                        str(note.get("summary") or "n/a"),
                        "",
                        "Screen change:",
                        str(diff.get("diff_summary") if diff else "大きな画面変化はありません。"),
                        "",
                    ]
                )
                last_screen_index = note["index"]
            else:
                lines.extend(
                    ["Screen:", "大きな画面変化はありません。", "", "Screen change:", "省略", ""]
                )
    else:
        lines.extend(["_No transcript segments generated._", ""])
        for note in screen_notes:
            lines.extend(
                [
                    f"## {_timestamp_label(float(note['timestamp']))}",
                    "Screen:",
                    str(note.get("summary") or "n/a"),
                    "",
                ]
            )

    rendered = "\n".join(lines).rstrip() + "\n"
    write_text(output_path, rendered)
    return rendered
