# TimelineForVideo

Clean rebuild workspace for `TimelineForVideo`. The previous implementation was
removed intentionally and is not the baseline for this v1.

TimelineForVideo is being rebuilt as a local Docker-first CLI that reads source
videos as read-only inputs and writes timeline-oriented evidence packages for
human review and LLM handoff.

## Quick Start

Run from Windows PowerShell:

```powershell
cd C:\apps\TimelineForVideo
.\start.ps1
.\cli.ps1 health
.\cli.ps1 settings init
.\cli.ps1 settings status
.\cli.ps1 settings save --input-root C:\TimelineData\input-video --output-root C:\TimelineData\video
.\cli.ps1 doctor
.\cli.ps1 files list
```

Stop the worker:

```powershell
.\stop.ps1
```

## Settings

`settings.json` is local runtime configuration and is not committed. The
committed template is `settings.example.json`.

```json
{
  "schemaVersion": 1,
  "inputRoots": [
    "C:\\TimelineData\\input-video\\"
  ],
  "outputRoot": "C:\\TimelineData\\video"
}
```

## Safety

Source videos are read-only inputs. Current commands only validate settings,
check configured paths, and discover video files by path and extension. They do
not modify, delete, copy, convert, probe, sample, or export source videos.

Milestone 2 discovery supports file inputs and recursive directory inputs for:

```text
.avi .m4v .mkv .mov .mp4 .webm .wmv
```

## Design Docs

Start from:

1. `AGENTS.md`
2. `docs/CODEX_HANDOFF.md`
3. `docs/DECISIONS.md`
4. `docs/OUTPUT_CONTRACT.md`
5. `docs/ACCEPTANCE_CRITERIA.md`
6. `docs/IMPLEMENTATION_MILESTONES.md`
