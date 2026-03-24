from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from video2timeline_worker.timeline import render_timeline


class TimelineTests(unittest.TestCase):
    def test_render_timeline_uses_original_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "timeline.md"
            render_timeline(
                output_path=output_path,
                source_info={
                    "original_path": "C:/video.mp4",
                    "media_id": "sample",
                    "duration_seconds": 120.0,
                },
                transcript_payload={
                    "segments": [
                        {
                            "speaker": "SPEAKER_01",
                            "text": "hello world",
                            "original_start": 12.345,
                            "original_end": 15.678,
                        }
                    ]
                },
                screen_notes=[
                    {
                        "index": 1,
                        "timestamp": 12.0,
                        "summary": "browser screen",
                    }
                ],
                screen_diffs=[
                    {
                        "index": 1,
                        "diff_summary": "first frame",
                    }
                ],
            )

            text = output_path.read_text(encoding="utf-8")
            self.assertIn("00:00:12.345 - 00:00:15.678", text)
            self.assertIn("SPEAKER_01: hello world", text)
            self.assertIn("browser screen", text)


if __name__ == "__main__":
    unittest.main()
