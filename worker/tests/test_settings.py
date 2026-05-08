from __future__ import annotations

import unittest
from unittest.mock import patch

from timeline_for_video_worker.settings import (
    SettingsError,
    load_huggingface_token,
    normalize_settings,
    redact_settings,
)


class SettingsTests(unittest.TestCase):
    def test_normalize_settings_deduplicates_input_roots_case_insensitively(self) -> None:
        settings = normalize_settings(
            {
                "schemaVersion": 1,
                "inputRoots": [
                    " C:\\TimelineData\\input-video ",
                    "c:\\timelinedata\\input-video",
                ],
                "outputRoot": " C:\\TimelineData\\video ",
            }
        )

        self.assertEqual(
            settings,
            {
                "schemaVersion": 1,
                "inputRoots": ["C:\\TimelineData\\input-video"],
                "outputRoot": "C:\\TimelineData\\video",
                "huggingFaceToken": "",
                "computeMode": "gpu",
                "audioModelMode": "required",
            },
        )

    def test_normalize_settings_rejects_empty_output_root(self) -> None:
        with self.assertRaises(SettingsError):
            normalize_settings(
                {
                    "schemaVersion": 1,
                    "inputRoots": ["C:\\TimelineData\\input-video"],
                    "outputRoot": " ",
                }
            )

    def test_load_huggingface_token_prefers_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TIMELINE_FOR_VIDEO_HUGGING_FACE_TOKEN": "hf_env_token",
                "HUGGING_FACE_HUB_TOKEN": "",
                "HF_TOKEN": "",
            },
            clear=False,
        ):
            token = load_huggingface_token({"huggingFaceToken": "hf_settings_token"})

        self.assertEqual(token, "hf_env_token")

    def test_redact_settings_reports_token_source_without_leaking_value(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TIMELINE_FOR_VIDEO_HUGGING_FACE_TOKEN": "",
                "HUGGING_FACE_HUB_TOKEN": "hf_env_secret",
                "HF_TOKEN": "",
            },
            clear=False,
        ):
            redacted = redact_settings(
                {
                    "schemaVersion": 1,
                    "inputRoots": ["C:\\TimelineData\\input-video"],
                    "outputRoot": "C:\\TimelineData\\video",
                    "huggingFaceToken": "",
                    "computeMode": "cpu",
                    "audioModelMode": "auto",
                }
            )

        self.assertEqual(redacted["huggingFaceToken"], {"configured": True, "source": "environment"})
        self.assertNotIn("hf_env_secret", str(redacted))


if __name__ == "__main__":
    unittest.main()
