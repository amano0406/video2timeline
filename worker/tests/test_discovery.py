from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from timeline_for_video_worker.discovery import (
    SUPPORTED_VIDEO_EXTENSIONS,
    assess_output_root,
    discover_video_files,
    resolve_configured_path,
)


class DiscoveryTests(unittest.TestCase):
    def test_discover_video_files_recurses_and_filters_by_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "nested"
            nested.mkdir()
            mp4 = root / "a.mp4"
            mov = root / "b.MOV"
            mkv = nested / "c.mkv"
            text = nested / "ignore.txt"
            mp4.write_bytes(b"mp4")
            mov.write_bytes(b"mov")
            mkv.write_bytes(b"mkv")
            text.write_text("not a video", encoding="utf-8")

            result = discover_video_files(
                {
                    "schemaVersion": 1,
                    "inputRoots": [str(root)],
                    "outputRoot": str(root / "out"),
                }
            )

            self.assertEqual(result.input_roots[0].video_file_count, 3)
            self.assertEqual([file.extension for file in result.files], [".mp4", ".mov", ".mkv"])
            self.assertEqual(mp4.read_bytes(), b"mp4")
            self.assertEqual(mov.read_bytes(), b"mov")
            self.assertEqual(mkv.read_bytes(), b"mkv")
            self.assertEqual(text.read_text(encoding="utf-8"), "not a video")

    def test_discover_video_files_supports_file_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "clip.webm"
            source.write_bytes(b"webm")

            result = discover_video_files(
                {
                    "schemaVersion": 1,
                    "inputRoots": [str(source)],
                    "outputRoot": str(Path(temp_dir) / "out"),
                }
            )

            self.assertEqual(len(result.files), 1)
            self.assertEqual(result.files[0].resolved_path, str(source))

    def test_discover_video_files_marks_unsupported_file_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "notes.txt"
            source.write_text("notes", encoding="utf-8")

            result = discover_video_files(
                {
                    "schemaVersion": 1,
                    "inputRoots": [str(source)],
                    "outputRoot": str(Path(temp_dir) / "out"),
                }
            )

            self.assertEqual(result.files, [])
            self.assertIn("unsupported_extension", result.input_roots[0].warnings)

    def test_resolve_configured_path_maps_windows_drive_paths_on_linux(self) -> None:
        if os.name != "nt":
            self.assertEqual(
                str(resolve_configured_path("C:\\TimelineData\\input-video\\")),
                "/mnt/c/TimelineData/input-video",
            )

    def test_assess_output_root_allows_missing_child_when_parent_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            status = assess_output_root(str(Path(temp_dir) / "video-output"))

            self.assertTrue(status["ok"])
            self.assertFalse(status["exists"])

    def test_supported_video_extensions_are_minimal_and_lowercase(self) -> None:
        self.assertIn(".mp4", SUPPORTED_VIDEO_EXTENSIONS)
        self.assertIn(".mov", SUPPORTED_VIDEO_EXTENSIONS)
        self.assertEqual(tuple(sorted(SUPPORTED_VIDEO_EXTENSIONS)), SUPPORTED_VIDEO_EXTENSIONS)
        self.assertTrue(all(extension == extension.lower() for extension in SUPPORTED_VIDEO_EXTENSIONS))
