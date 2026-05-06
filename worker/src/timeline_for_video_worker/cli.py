from __future__ import annotations

import argparse
import json
import os
import platform
import time
from typing import Any

from . import __version__
from .settings import (
    PRODUCT_NAME,
    SettingsError,
    load_example_settings,
    load_settings,
    save_settings,
    settings_example_path,
    settings_path,
)


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def emit_result(args: argparse.Namespace, payload: dict[str, Any], message: str) -> None:
    if getattr(args, "json", False):
        emit_json(payload)
        return
    print(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timeline-for-video",
        description="Local TimelineForVideo worker CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health", help="Check worker health.")
    health_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    health_parser.set_defaults(handler=handle_health)

    serve_parser = subparsers.add_parser("serve", help="Keep the worker container alive.")
    serve_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.environ.get("TIMELINE_FOR_VIDEO_WORKER_INTERVAL_SECONDS", "60")),
    )
    serve_parser.set_defaults(handler=handle_serve)

    settings_parser = subparsers.add_parser("settings", help="Manage local settings.")
    settings_subparsers = settings_parser.add_subparsers(
        dest="settings_command",
        required=True,
    )

    init_parser = settings_subparsers.add_parser("init", help="Create settings.json.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing settings.")
    init_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    init_parser.set_defaults(handler=handle_settings_init)

    status_parser = settings_subparsers.add_parser("status", help="Show settings status.")
    status_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    status_parser.set_defaults(handler=handle_settings_status)

    save_parser = settings_subparsers.add_parser("save", help="Update settings.json.")
    save_parser.add_argument(
        "--input-root",
        action="append",
        default=None,
        help="Input video root. Repeat to set multiple roots.",
    )
    save_parser.add_argument("--output-root", default=None, help="Output root.")
    save_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    save_parser.set_defaults(handler=handle_settings_save)

    return parser


def handle_health(args: argparse.Namespace) -> int:
    payload = {
        "ok": True,
        "product": PRODUCT_NAME,
        "version": __version__,
        "python": platform.python_version(),
        "inDocker": os.environ.get("TIMELINE_FOR_VIDEO_IN_DOCKER") == "1",
        "settingsPath": str(settings_path()),
    }
    emit_result(args, payload, f"{PRODUCT_NAME} worker OK")
    return 0


def handle_serve(args: argparse.Namespace) -> int:
    interval = max(args.interval_seconds, 1.0)
    print(f"{PRODUCT_NAME} worker is idle. Press Ctrl+C to stop.", flush=True)
    try:
        while True:
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def handle_settings_init(args: argparse.Namespace) -> int:
    target = settings_path()
    created = False
    overwritten = False

    if target.exists() and not args.force:
        settings = load_settings(target)
    else:
        overwritten = target.exists()
        settings = save_settings(load_example_settings(), target)
        created = not overwritten

    payload = {
        "ok": True,
        "created": created,
        "overwritten": overwritten,
        "settingsPath": str(target),
        "settingsExamplePath": str(settings_example_path()),
        "settings": settings,
    }
    action = "Created" if created else "Overwrote" if overwritten else "Already exists"
    emit_result(args, payload, f"{action}: {target}")
    return 0


def handle_settings_status(args: argparse.Namespace) -> int:
    target = settings_path()
    exists = target.exists()
    settings = load_settings(target) if exists else None
    payload = {
        "ok": True,
        "exists": exists,
        "settingsPath": str(target),
        "settingsExamplePath": str(settings_example_path()),
        "settings": settings,
    }
    message = f"Settings exist: {target}" if exists else f"Settings missing: {target}"
    emit_result(args, payload, message)
    return 0


def handle_settings_save(args: argparse.Namespace) -> int:
    target = settings_path()
    settings = load_settings(target) if target.exists() else load_example_settings()

    if args.input_root is not None:
        settings["inputRoots"] = args.input_root
    if args.output_root is not None:
        settings["outputRoot"] = args.output_root

    settings = save_settings(settings, target)
    payload = {
        "ok": True,
        "settingsPath": str(target),
        "settings": settings,
    }
    emit_result(args, payload, f"Saved: {target}")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except SettingsError as exc:
        emit_json({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
