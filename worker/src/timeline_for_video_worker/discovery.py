from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any


SUPPORTED_VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".webm",
    ".wmv",
)

WINDOWS_DRIVE_PATH_RE = re.compile(r"^([A-Za-z]):[\\/]*(.*)$")


@dataclass
class InputRootStatus:
    configured_path: str
    resolved_path: str
    exists: bool
    kind: str
    readable: bool
    video_file_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "configuredPath": self.configured_path,
            "resolvedPath": self.resolved_path,
            "exists": self.exists,
            "kind": self.kind,
            "readable": self.readable,
            "videoFileCount": self.video_file_count,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class VideoFile:
    source_path: str
    resolved_path: str
    input_root: str
    extension: str
    size_bytes: int
    modified_time: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourcePath": self.source_path,
            "resolvedPath": self.resolved_path,
            "inputRoot": self.input_root,
            "extension": self.extension,
            "sizeBytes": self.size_bytes,
            "modifiedTime": self.modified_time,
        }


@dataclass
class DiscoveryResult:
    input_roots: list[InputRootStatus]
    files: list[VideoFile]

    def to_dict(self) -> dict[str, Any]:
        missing_inputs = sum(1 for root in self.input_roots if not root.exists)
        unreadable_inputs = sum(1 for root in self.input_roots if root.exists and not root.readable)
        return {
            "supportedExtensions": list(SUPPORTED_VIDEO_EXTENSIONS),
            "counts": {
                "inputRoots": len(self.input_roots),
                "files": len(self.files),
                "missingInputs": missing_inputs,
                "unreadableInputs": unreadable_inputs,
            },
            "inputRoots": [root.to_dict() for root in self.input_roots],
            "files": [video_file.to_dict() for video_file in self.files],
        }


def is_supported_video_path(path: Path) -> bool:
    return path.suffix.casefold() in SUPPORTED_VIDEO_EXTENSIONS


def resolve_configured_path(path_text: str) -> Path:
    match = WINDOWS_DRIVE_PATH_RE.match(path_text.strip())
    if match and os.name != "nt":
        drive = match.group(1).casefold()
        rest = match.group(2).replace("\\", "/").strip("/")
        return Path("/mnt") / drive / rest
    return Path(path_text)


def display_path(path: Path) -> str:
    if os.name == "nt":
        return str(path)

    parts = path.parts
    if len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        rest = "\\".join(parts[3:])
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"

    return str(path)


def discover_video_files(settings: dict[str, Any]) -> DiscoveryResult:
    input_roots = settings["inputRoots"]
    root_statuses: list[InputRootStatus] = []
    files: list[VideoFile] = []

    for configured_root in input_roots:
        resolved_root = resolve_configured_path(configured_root)
        status = inspect_input_root(configured_root, resolved_root)
        root_statuses.append(status)

        if not status.exists or not status.readable:
            continue

        if resolved_root.is_file():
            if is_supported_video_path(resolved_root):
                files.append(video_file_from_path(resolved_root, configured_root))
                status.video_file_count = 1
            else:
                status.warnings.append("unsupported_extension")
            continue

        if resolved_root.is_dir():
            root_files = list(walk_video_files(resolved_root, status))
            files.extend(root_files)
            status.video_file_count = len(root_files)

    files.sort(key=lambda file: file.source_path.casefold())
    return DiscoveryResult(root_statuses, files)


def inspect_input_root(configured_root: str, resolved_root: Path) -> InputRootStatus:
    exists = resolved_root.exists()
    if resolved_root.is_file():
        kind = "file"
    elif resolved_root.is_dir():
        kind = "directory"
    elif exists:
        kind = "other"
    else:
        kind = "missing"

    readable = exists and os.access(resolved_root, os.R_OK)
    warnings: list[str] = []
    if exists and not readable:
        warnings.append("unreadable")
    if kind == "other":
        warnings.append("not_file_or_directory")

    return InputRootStatus(
        configured_path=configured_root,
        resolved_path=str(resolved_root),
        exists=exists,
        kind=kind,
        readable=readable,
        warnings=warnings,
    )


def walk_video_files(root: Path, status: InputRootStatus) -> list[VideoFile]:
    found: list[VideoFile] = []

    def on_error(error: OSError) -> None:
        status.warnings.append(f"scan_error:{error.filename}")

    for current_root, dir_names, file_names in os.walk(root, topdown=True, onerror=on_error, followlinks=False):
        dir_names[:] = sorted(dir_names, key=str.casefold)
        for file_name in sorted(file_names, key=str.casefold):
            candidate = Path(current_root) / file_name
            if not is_supported_video_path(candidate):
                continue
            if candidate.is_symlink():
                status.warnings.append(f"skipped_symlink:{candidate}")
                continue
            found.append(video_file_from_path(candidate, status.configured_path))

    return found


def video_file_from_path(path: Path, input_root: str) -> VideoFile:
    stat_result = path.stat()
    modified_time = datetime.fromtimestamp(stat_result.st_mtime, timezone.utc).isoformat()
    return VideoFile(
        source_path=display_path(path),
        resolved_path=str(path),
        input_root=input_root,
        extension=path.suffix.casefold(),
        size_bytes=stat_result.st_size,
        modified_time=modified_time,
    )


def assess_output_root(output_root_text: str) -> dict[str, Any]:
    resolved = resolve_configured_path(output_root_text)
    exists = resolved.exists()
    parent = resolved.parent

    if resolved.is_dir():
        kind = "directory"
    elif resolved.is_file():
        kind = "file"
    elif exists:
        kind = "other"
    else:
        kind = "missing"

    parent_exists = parent.exists()
    writable_target = exists and resolved.is_dir() and os.access(resolved, os.W_OK)
    writable_parent = (not exists) and parent_exists and parent.is_dir() and os.access(parent, os.W_OK)
    ok = writable_target or writable_parent

    return {
        "configuredPath": output_root_text,
        "resolvedPath": str(resolved),
        "exists": exists,
        "kind": kind,
        "parentPath": str(parent),
        "parentExists": parent_exists,
        "writable": bool(writable_target or writable_parent),
        "ok": bool(ok),
    }
