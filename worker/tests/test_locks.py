from __future__ import annotations

import json
from pathlib import Path
import os
import tempfile
import time
import unittest

from timeline_for_video_worker.locks import exclusive_lock


class LockTests(unittest.TestCase):
    def test_exclusive_lock_recovers_stale_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lock_path = root / "catalog.lock"
            lock_path.write_text("999999999", encoding="utf-8")

            with exclusive_lock(root, "catalog"):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())

    def test_exclusive_lock_recovers_current_pid_file_from_previous_container(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lock_path = root / "catalog.lock"
            lock_path.write_text(str(os.getpid()), encoding="utf-8")

            with exclusive_lock(root, "catalog"):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())

    def test_exclusive_lock_recovers_old_lock_from_previous_container(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lock_path = root / "catalog.lock"
            lock_path.write_text(
                json.dumps({"pid": 1, "hostname": "previous-container"}),
                encoding="utf-8",
            )
            old_time = time.time() - 3600
            os.utime(lock_path, (old_time, old_time))

            with exclusive_lock(root, "catalog", stale_after_sec=1):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
