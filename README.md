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
.\cli.ps1 probe list --max-items 1
.\cli.ps1 sample frames --max-items 1 --samples-per-video 5
.\cli.ps1 items refresh --max-items 1
.\cli.ps1 items list
.\cli.ps1 items download
.\cli.ps1 items remove --dry-run
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

Source videos are read-only inputs. Current commands validate settings, check
configured paths, discover video files by path and extension, read ffprobe
metadata, and extract bounded review frames with ffmpeg. They do not modify,
delete, copy, convert, transcribe, OCR, recognize, or export source videos.

Milestone 2 discovery supports file inputs and recursive directory inputs for:

```text
.avi .m4v .mkv .mov .mp4 .webm .wmv
```

Milestone 3 probing uses ffprobe for read-only metadata only. Source
fingerprints and item ids are derived from path, size, and modification time;
full-file content hashing is not performed by default for large-video safety.

Milestone 4 sampling writes generated artifacts only under `outputRoot`:

```text
<outputRoot>/
  items/
    <item-id>/
      raw_outputs/
        frame_samples.json
      artifacts/
        contact_sheet.jpg
        frames/
          frame-000001.jpg
```

The default sampling command is bounded to one video and five frames per video.

Milestone 5 item refresh writes item records under `outputRoot`:

```text
<outputRoot>/
  items/
    <item-id>/
      video_record.json
      timeline.json
      convert_info.json
      raw_outputs/
        ffprobe.json
        frame_samples.json
      artifacts/
        contact_sheet.jpg
        frames/
```

`items refresh` updates the JSON records and the ffprobe raw output. It references
existing frame samples and contact sheets when present, but does not extract
frames or copy source videos.

Milestone 6 export and removal commands are source-safe:

- `items download` writes a ZIP under `<outputRoot>\downloads\` and refreshes
  `<outputRoot>\latest\items.zip`.
- ZIP exports include generated item records, raw outputs, and artifacts only.
  They do not include source videos.
- `items remove --dry-run` reports generated artifacts that would be removed.
- `items remove` deletes only known generated files and prunes empty generated
  directories. It does not delete source videos.

## Design Docs

Start from:

1. `AGENTS.md`
2. `docs/CODEX_HANDOFF.md`
3. `docs/DECISIONS.md`
4. `docs/OUTPUT_CONTRACT.md`
5. `docs/ACCEPTANCE_CRITERIA.md`
6. `docs/IMPLEMENTATION_MILESTONES.md`
