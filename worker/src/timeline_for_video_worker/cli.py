from __future__ import annotations

import argparse
import json
import os
import platform
import time
from typing import Any

from . import __version__
from .discovery import (
    SUPPORTED_VIDEO_EXTENSIONS,
    assess_output_root,
    discover_video_files,
)
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

    doctor_parser = subparsers.add_parser("doctor", help="Check runtime and configured paths.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    doctor_parser.set_defaults(handler=handle_doctor)

    files_parser = subparsers.add_parser("files", help="Inspect source video files.")
    files_subparsers = files_parser.add_subparsers(dest="files_command", required=True)

    files_list_parser = files_subparsers.add_parser("list", help="List configured video files.")
    files_list_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    files_list_parser.set_defaults(handler=handle_files_list)

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


def handle_doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = [
        {
            "name": "runtime.python",
            "ok": True,
            "message": f"Python {platform.python_version()}",
        }
    ]

    target = settings_path()
    payload: dict[str, Any] = {
        "ok": False,
        "product": PRODUCT_NAME,
        "version": __version__,
        "settingsPath": str(target),
        "supportedExtensions": list(SUPPORTED_VIDEO_EXTENSIONS),
        "checks": checks,
    }

    if not target.exists():
        checks.append(
            {
                "name": "settings",
                "ok": False,
                "message": f"Settings file is missing: {target}",
            }
        )
        output_doctor(args, payload)
        return 1

    try:
        settings = load_settings(target)
    except SettingsError as exc:
        checks.append({"name": "settings", "ok": False, "message": str(exc)})
        output_doctor(args, payload)
        return 1

    checks.append({"name": "settings", "ok": True, "message": f"Settings file is valid: {target}"})
    discovery = discover_video_files(settings)
    output_status = assess_output_root(settings["outputRoot"])

    for root in discovery.input_roots:
        root_ok = (
            root.exists
            and root.readable
            and root.kind in {"file", "directory"}
            and "unsupported_extension" not in root.warnings
        )
        checks.append(
            {
                "name": "input_root",
                "ok": root_ok,
                "message": input_root_message(root.to_dict()),
                "details": root.to_dict(),
            }
        )

    checks.append(
        {
            "name": "output_root",
            "ok": output_status["ok"],
            "message": output_root_message(output_status),
            "details": output_status,
        }
    )

    payload.update(
        {
            "ok": all(check["ok"] for check in checks),
            "settings": settings,
            "discovery": discovery.to_dict(),
            "outputRoot": output_status,
        }
    )
    output_doctor(args, payload)
    return 0 if payload["ok"] else 1


def handle_files_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    discovery = discover_video_files(settings)
    payload = {
        "ok": True,
        "settingsPath": str(settings_path()),
        **discovery.to_dict(),
    }

    if args.json:
        emit_json(payload)
        return 0

    print(f"Found {payload['counts']['files']} video file(s).")
    print(f"Supported extensions: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}")
    print("")
    print("Input roots:")
    for root in payload["inputRoots"]:
        status = "OK" if root["exists"] and root["readable"] and root["kind"] in {"file", "directory"} else "ISSUE"
        print(
            f"  [{status}] {root['configuredPath']} "
            f"({root['kind']}, {root['videoFileCount']} video file(s))"
        )
        if root["resolvedPath"] != root["configuredPath"]:
            print(f"        resolved: {root['resolvedPath']}")
        for warning in root["warnings"]:
            print(f"        warning: {warning}")

    if payload["files"]:
        print("")
        print("Files:")
        for video_file in payload["files"]:
            print(f"  {video_file['sourcePath']} ({video_file['sizeBytes']} bytes)")

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


def input_root_message(root: dict[str, Any]) -> str:
    if not root["exists"]:
        return f"Input root is missing: {root['configuredPath']}"
    if not root["readable"]:
        return f"Input root is not readable: {root['configuredPath']}"
    if root["kind"] not in {"file", "directory"}:
        return f"Input root is not a file or directory: {root['configuredPath']}"
    if "unsupported_extension" in root["warnings"]:
        return f"Input file extension is not supported: {root['configuredPath']}"
    return f"Input root is readable: {root['configuredPath']}"


def output_root_message(output_root: dict[str, Any]) -> str:
    if output_root["ok"] and output_root["exists"]:
        return f"Output root exists and is writable: {output_root['configuredPath']}"
    if output_root["ok"]:
        return f"Output root can be created under existing parent: {output_root['configuredPath']}"
    if output_root["kind"] == "file":
        return f"Output root points to a file: {output_root['configuredPath']}"
    if not output_root["parentExists"]:
        return f"Output root parent is missing: {output_root['parentPath']}"
    return f"Output root is not writable: {output_root['configuredPath']}"


def output_doctor(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if args.json:
        emit_json(payload)
        return

    print(f"Doctor: {'OK' if payload['ok'] else 'ISSUES FOUND'}")
    for check in payload["checks"]:
        status = "OK" if check["ok"] else "FAIL"
        print(f"  [{status}] {check['name']}: {check['message']}")


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
