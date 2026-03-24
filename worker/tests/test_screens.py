from __future__ import annotations

import unittest

from video2timeline_worker.screens import candidate_timestamps


class CandidateTimestampsTests(unittest.TestCase):
    def test_short_videos_keep_single_zero_timestamp(self) -> None:
        self.assertEqual(candidate_timestamps(0.8), [0.0])

    def test_last_timestamp_is_clamped_before_duration(self) -> None:
        timestamps = candidate_timestamps(8.783)
        self.assertGreater(len(timestamps), 1)
        self.assertLess(timestamps[-1], 8.783)
        self.assertAlmostEqual(timestamps[-1], 8.733, places=3)


if __name__ == "__main__":
    unittest.main()
