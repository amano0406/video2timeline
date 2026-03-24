from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .config import AppConfig, ChangeDetectionConfig, OcrPolicy, SourceDirectory, load_config
from .discovery import discover_videos
from .settings import load_runtime_defaults


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="video2timeline worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan configured source directories for videos.")
    scan_parser.add_argument("--config", type=Path, required=False)
    scan_parser.add_argument("--output", type=Path, required=False)

    compare_parser = subparsers.add_parser("compare-images", help="Compare two images.")
    compare_parser.add_argument("--config", type=Path, required=False)
    compare_parser.add_argument("--previous", type=Path, required=True)
    compare_parser.add_argument("--current", type=Path, required=True)

    run_parser = subparsers.add_parser("run-job", help="Run one specific job directory.")
    run_parser.add_argument("--job-dir", type=Path, required=True)

    daemon_parser = subparsers.add_parser("daemon", help="Poll output roots and process pending jobs.")
    daemon_parser.add_argument("--poll-interval", type=int, default=5)

    return parser.parse_args()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _runtime_config() -> AppConfig:
    defaults = load_runtime_defaults()
    return AppConfig(
        project_name="video2timeline",
        source_directories=[
            SourceDirectory(
                name=str(row.get("id") or row.get("displayName") or "source"),
                path=str(row.get("path") or ""),
                recursive=True,
            )
            for row in defaults.get("inputRoots", [])
            if row.get("enabled", True) and row.get("path")
        ],
        output_root=str(defaults.get("outputRoots", [{}])[0].get("path") or "/shared/outputs/default"),
        video_extensions=[str(ext) for ext in defaults.get("videoExtensions", [])],
        change_detection=ChangeDetectionConfig(),
        ocr_policy=OcrPolicy(),
    )


def _load_app_config(config_path: Path | None) -> AppConfig:
    if config_path:
        return load_config(config_path)
    return _runtime_config()


def cmd_scan(config_path: Path | None, output: Path | None) -> int:
    payload = discover_videos(_load_app_config(config_path))
    if output:
        write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_compare(config_path: Path | None, previous: Path, current: Path) -> int:
    from .change_detection import compare_images

    config = _load_app_config(config_path)
    result = compare_images(previous, current, config.change_detection)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_run_job(job_dir: Path) -> int:
    from .processor import process_job

    process_job(job_dir)
    return 0


def cmd_daemon(poll_interval: int) -> int:
    from .processor import process_job

    while True:
        found = process_job()
        if not found:
            time.sleep(max(1, poll_interval))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "scan":
        return cmd_scan(args.config, args.output)
    if args.command == "compare-images":
        return cmd_compare(args.config, args.previous, args.current)
    if args.command == "run-job":
        return cmd_run_job(args.job_dir)
    if args.command == "daemon":
        return cmd_daemon(args.poll_interval)
    raise ValueError(f"Unsupported command: {args.command}")
