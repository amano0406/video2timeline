from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from timeline_for_video_worker.cli import main


FFPROBE_FIXTURE = {
    "streams": [
        {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 320, "height": 180},
    ],
    "format": {"format_name": "mov,mp4", "duration": "1.000000", "size": "5"},
}


def write_fake_ffprobe(directory: Path) -> str:
    script = directory / "fake_ffprobe.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "if '-version' in sys.argv:",
                "    print('ffprobe fake 1.0')",
                "else:",
                f"    print(json.dumps({FFPROBE_FIXTURE!r}))",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return f"{sys.executable} {script}"


def write_fake_ffmpeg(directory: Path) -> str:
    script = directory / "fake_ffmpeg.py"
    script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "if '-version' in sys.argv:",
                "    print('ffmpeg fake 1.0')",
                "    raise SystemExit(0)",
                "Path(sys.argv[-1]).write_bytes(b'jpeg')",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return f"{sys.executable} {script}"


def write_example_settings(
    tmp_path: Path,
    input_roots: list[str] | None = None,
    output_root: str | None = None,
) -> tuple[Path, Path]:
    settings_path = tmp_path / "settings.json"
    example_path = tmp_path / "settings.example.json"
    example_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "inputRoots": input_roots or ["C:\\TimelineData\\input-video\\"],
                "outputRoot": output_root or "C:\\TimelineData\\video",
            }
        ),
        encoding="utf-8",
    )
    return settings_path, example_path


def run_json(args: list[str], env: dict[str, str] | None = None) -> tuple[int, dict]:
    output = io.StringIO()
    with patch.dict(os.environ, env or {}, clear=False):
        with contextlib.redirect_stdout(output):
            exit_code = main(args)
    return exit_code, json.loads(output.getvalue())


class CliTests(unittest.TestCase):
    def test_health_json(self) -> None:
        exit_code, payload = run_json(["health", "--json"])

        self.assertEqual(exit_code, 0)
        self.assertIs(payload["ok"], True)
        self.assertEqual(payload["product"], "TimelineForVideo")

    def test_settings_init_status_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path, example_path = write_example_settings(Path(temp_dir))
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, init_payload = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)
            self.assertIs(init_payload["created"], True)
            self.assertTrue(settings_path.exists())

            exit_code, status_payload = run_json(["settings", "status", "--json"], env)
            self.assertEqual(exit_code, 0)
            self.assertIs(status_payload["exists"], True)

            exit_code, save_payload = run_json(
                [
                    "settings",
                    "save",
                    "--input-root",
                    "C:\\Videos\\A",
                    "--input-root",
                    "D:\\Videos\\B",
                    "--output-root",
                    "E:\\TimelineVideo",
                    "--json",
                ],
                env,
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                save_payload["settings"]["inputRoots"],
                ["C:\\Videos\\A", "D:\\Videos\\B"],
            )
            self.assertEqual(save_payload["settings"]["outputRoot"], "E:\\TimelineVideo")

            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(saved, save_payload["settings"])

    def test_files_list_json_uses_settings_input_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(root)],
                output_root=str(root / "out"),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)

            exit_code, payload = run_json(["files", "list", "--json"], env)

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["counts"]["files"], 1)
            self.assertEqual(payload["files"][0]["resolvedPath"], str(source))

    def test_doctor_json_reports_ok_for_existing_input_and_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "clip.mov"
            source.write_bytes(b"video")
            fake_ffprobe = write_fake_ffprobe(root)
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(root)],
                output_root=str(root / "out"),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)

            exit_code, payload = run_json(["doctor", "--json", "--ffprobe-bin", fake_ffprobe], env)

            self.assertEqual(exit_code, 0)
            self.assertIs(payload["ok"], True)
            self.assertEqual(payload["discovery"]["counts"]["files"], 1)
            self.assertTrue(payload["ffprobeVersion"]["ok"])

    def test_doctor_json_fails_for_missing_input_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing = root / "missing"
            fake_ffprobe = write_fake_ffprobe(root)
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(missing)],
                output_root=str(root / "out"),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)

            exit_code, payload = run_json(["doctor", "--json", "--ffprobe-bin", fake_ffprobe], env)

            self.assertEqual(exit_code, 1)
            self.assertIs(payload["ok"], False)
            self.assertIn("missing", payload["checks"][3]["message"])

    def test_probe_list_json_uses_discovered_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            fake_ffprobe = write_fake_ffprobe(root)
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(root)],
                output_root=str(root / "out"),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)

            exit_code, payload = run_json(
                ["probe", "list", "--json", "--ffprobe-bin", fake_ffprobe],
                env,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["counts"]["probedFiles"], 1)
            self.assertTrue(payload["records"][0]["itemId"].startswith("video-"))
            self.assertEqual(payload["records"][0]["ffprobe"]["summary"]["counts"]["videoStreams"], 1)

    def test_sample_frames_json_writes_frame_samples_under_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            output_root = root / "output"
            fake_ffprobe = write_fake_ffprobe(root)
            fake_ffmpeg = write_fake_ffmpeg(root)
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(source.parent)],
                output_root=str(output_root),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)

            exit_code, payload = run_json(
                [
                    "sample",
                    "frames",
                    "--json",
                    "--ffprobe-bin",
                    fake_ffprobe,
                    "--ffmpeg-bin",
                    fake_ffmpeg,
                    "--max-items",
                    "1",
                    "--samples-per-video",
                    "2",
                ],
                env,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["counts"]["extractedFrames"], 2)
            frame_samples = Path(payload["records"][0]["outputs"]["frameSamplesJson"])
            self.assertTrue(frame_samples.exists())
            self.assertTrue(str(frame_samples).startswith(str(output_root)))

    def test_sample_frames_json_returns_structured_error_for_unbounded_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            output_root = root / "output"
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(source.parent)],
                output_root=str(output_root),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)

            exit_code, payload = run_json(
                [
                    "sample",
                    "frames",
                    "--json",
                    "--samples-per-video",
                    "13",
                ],
                env,
            )

            self.assertEqual(exit_code, 2)
            self.assertFalse(payload["ok"])
            self.assertIn("samples_per_video", payload["error"])

    def test_items_refresh_and_list_json_use_output_root_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            output_root = root / "output"
            fake_ffprobe = write_fake_ffprobe(root)
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(source.parent)],
                output_root=str(output_root),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)

            exit_code, refresh_payload = run_json(
                [
                    "items",
                    "refresh",
                    "--json",
                    "--ffprobe-bin",
                    fake_ffprobe,
                    "--max-items",
                    "1",
                ],
                env,
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(refresh_payload["counts"]["refreshedItems"], 1)

            exit_code, list_payload = run_json(["items", "list", "--json"], env)
            self.assertEqual(exit_code, 0)
            self.assertEqual(list_payload["counts"]["items"], 1)
            self.assertTrue(list_payload["items"][0]["itemId"].startswith("video-"))

    def test_items_download_and_remove_dry_run_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            output_root = root / "output"
            fake_ffprobe = write_fake_ffprobe(root)
            settings_path, example_path = write_example_settings(
                root,
                input_roots=[str(source.parent)],
                output_root=str(output_root),
            )
            env = {
                "TIMELINE_FOR_VIDEO_SETTINGS_PATH": str(settings_path),
                "TIMELINE_FOR_VIDEO_SETTINGS_EXAMPLE_PATH": str(example_path),
            }

            exit_code, _ = run_json(["settings", "init", "--json"], env)
            self.assertEqual(exit_code, 0)
            exit_code, _ = run_json(
                ["items", "refresh", "--json", "--ffprobe-bin", fake_ffprobe, "--max-items", "1"],
                env,
            )
            self.assertEqual(exit_code, 0)

            exit_code, download_payload = run_json(["items", "download", "--json"], env)
            self.assertEqual(exit_code, 0)
            self.assertFalse(download_payload["sourceVideosIncluded"])
            self.assertTrue(Path(download_payload["archivePath"]).exists())

            exit_code, remove_payload = run_json(["items", "remove", "--dry-run", "--json"], env)
            self.assertEqual(exit_code, 0)
            self.assertTrue(remove_payload["dryRun"])
            self.assertGreater(remove_payload["counts"]["targetFiles"], 0)


if __name__ == "__main__":
    unittest.main()
