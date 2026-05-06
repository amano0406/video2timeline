from __future__ import annotations

import unittest

from timeline_for_video_worker.settings import SettingsError, normalize_settings


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


if __name__ == "__main__":
    unittest.main()
