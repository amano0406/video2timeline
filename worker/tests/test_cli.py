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


def write_example_settings(tmp_path: Path) -> tuple[Path, Path]:
    settings_path = tmp_path / "settings.json"
    example_path = tmp_path / "settings.example.json"
    example_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "inputRoots": ["C:\\TimelineData\\input-video\\"],
                "outputRoot": "C:\\TimelineData\\video",
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


if __name__ == "__main__":
    unittest.main()
