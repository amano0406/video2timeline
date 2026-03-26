from __future__ import annotations

import unittest

from video2timeline_worker.transcribe import (
    _candidate_batch_sizes,
    _initial_batch_size,
    _is_cuda_oom,
)


class TranscribeHelpersTests(unittest.TestCase):
    def test_high_quality_gpu_uses_conservative_initial_batch_size(self) -> None:
        self.assertEqual(4, _initial_batch_size("cuda", "high"))

    def test_standard_gpu_uses_larger_initial_batch_size(self) -> None:
        self.assertEqual(16, _initial_batch_size("cuda", "standard"))

    def test_candidate_batch_sizes_are_unique_and_descending(self) -> None:
        self.assertEqual([16, 12, 8, 6, 4, 2, 1], _candidate_batch_sizes(16))
        self.assertEqual([4, 2, 1], _candidate_batch_sizes(4))

    def test_cuda_oom_detection_handles_whisperx_error_text(self) -> None:
        error = RuntimeError("CUDA failed with error out of memory")
        self.assertTrue(_is_cuda_oom(error))
        self.assertFalse(_is_cuda_oom(RuntimeError("some other failure")))


if __name__ == "__main__":
    unittest.main()
