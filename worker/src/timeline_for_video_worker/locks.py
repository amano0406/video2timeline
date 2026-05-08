from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Iterator


@contextmanager
def exclusive_lock(
    root: Path,
    name: str,
    timeout_sec: float = 30.0,
    stale_after_sec: float = 180.0,
    heartbeat_sec: float = 10.0,
) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / f"{name}.lock"
    deadline = time.monotonic() + timeout_sec
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if stale_lock(lock_path, stale_after_sec=stale_after_sec):
                try:
                    lock_path.unlink()
                    continue
                except FileNotFoundError:
                    continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock: {lock_path}")
            time.sleep(0.1)
    try:
        os.write(descriptor, lock_payload().encode("utf-8"))
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=heartbeat_lock,
            args=(lock_path, stop_heartbeat, heartbeat_sec),
            daemon=True,
        )
        heartbeat.start()
        yield
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=1.0)
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def stale_lock(lock_path: Path, stale_after_sec: float = 180.0) -> bool:
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return True

    if lock_age_sec(lock_path) > stale_after_sec:
        return True

    owner, owner_host = parse_lock_owner(raw)
    if owner <= 0:
        return True
    if owner == os.getpid():
        return True
    if owner_host and owner_host != socket.gethostname():
        return False
    try:
        os.kill(owner, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def parse_lock_owner(raw: str) -> tuple[int, str | None]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            return int(raw), None
        except ValueError:
            return 0, None

    if not isinstance(payload, dict):
        return 0, None
    try:
        pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    hostname = payload.get("hostname")
    return pid, str(hostname) if hostname else None


def lock_age_sec(lock_path: Path) -> float:
    try:
        return max(0.0, time.time() - lock_path.stat().st_mtime)
    except FileNotFoundError:
        return stale_after_sec_default()


def stale_after_sec_default() -> float:
    return 180.0


def lock_payload() -> str:
    now = time.time()
    return json.dumps(
        {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "createdAtUnix": now,
            "updatedAtUnix": now,
        },
        sort_keys=True,
    )


def heartbeat_lock(lock_path: Path, stop_event: threading.Event, heartbeat_sec: float) -> None:
    interval = max(1.0, heartbeat_sec)
    while not stop_event.wait(interval):
        try:
            payload = json.loads(lock_payload())
            payload["updatedAtUnix"] = time.time()
            lock_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        except OSError:
            return
