from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from timeline_for_video_worker.cli import main


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

            exit_code, payload = run_json(["doctor", "--json"], env)

            self.assertEqual(exit_code, 0)
            self.assertIs(payload["ok"], True)
            self.assertEqual(payload["discovery"]["counts"]["files"], 1)

    def test_doctor_json_fails_for_missing_input_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing = root / "missing"
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

            exit_code, payload = run_json(["doctor", "--json"], env)

            self.assertEqual(exit_code, 1)
            self.assertIs(payload["ok"], False)
            self.assertIn("missing", payload["checks"][2]["message"])


if __name__ == "__main__":
    unittest.main()
