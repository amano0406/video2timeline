# TimelineForVideo Clean Rebuild Handoff

## Current State

This repository was deliberately emptied on commit `81276ac`:

```text
Empty TimelineForVideo repository for rebuild
```

Do not restore the previous codebase. Start from a clean product design.

## Product Goal

`TimelineForVideo` v1 should process local video files or video directories and
write timeline-oriented evidence packages.

The first useful version is not a full video-understanding system. It is a
safe, local, structured evidence generator.

## v1 Scope

Build:

- Windows-friendly local CLI
- Docker-first runtime
- settings for input roots and output root
- video file discovery from files and directories
- ffprobe metadata capture
- bounded frame sampling
- extracted review frames
- contact sheet
- per-item structured outputs
- ZIP export excluding source videos
- generated-artifact remove command
- tests and smoke test with a generated sample video

Do not build in v1:

- hosted service
- web UI
- old TimelineForVideo compatibility layer
- full transcription
- diarization
- OCR
- scene detection
- face/person recognition
- external API analysis
- source video conversion

## Reference Sources

Read only as needed:

- `C:\apps\TimelineForAudio`
- `C:\apps\TimelineForImage`

The ChatGPT design discussion was captured through DockForChatGPT:

```text
C:\Codex\workspaces\dockforchatgpt\chat_conversations\snapshots\20260506-114835-69f96218-7de4-83a9-b46b-d660584e0639-a7f37b4b-62b8-443c-905d-c71a0e9c6d78.json
```

Use references for concepts and contracts. Do not copy implementation code.

## Implementation Stance

Keep the first product small and rebuildable:

- one repo
- one worker package
- one CLI surface
- clear JSON outputs
- generated artifacts separated from source videos
- direct smoke test path

Avoid a shared framework with other Timeline products.

