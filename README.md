# TimelineForVideo

Clean rebuild workspace for `TimelineForVideo`. The previous implementation was
removed intentionally and is not the baseline for this v1.

TimelineForVideo is being rebuilt as a local Docker-first CLI that reads source
videos as read-only inputs and writes timeline-oriented evidence packages for
human review and LLM handoff.

The normal runtime is a resident Docker worker. `items refresh` and `serve`
run the same changed-video processing pipeline; `serve` repeats it on an
interval.

## Quick Start

Run from Windows PowerShell:

```powershell
cd C:\apps\TimelineForVideo
.\start.ps1
.\cli.ps1 health
.\cli.ps1 settings init
.\cli.ps1 settings status
.\cli.ps1 settings save --input-root C:\Users\amano\Videos --input-root F:\Video --output-root C:\TimelineData\video
.\cli.ps1 doctor
.\cli.ps1 models list
.\cli.ps1 models list --include-remote --json
.\cli.ps1 files list
.\cli.ps1 files list --page 1 --page-size 100 --json
.\cli.ps1 probe list --max-items 1
.\cli.ps1 items refresh --max-items 1
.\cli.ps1 items list
.\cli.ps1 items list --page 1 --page-size 100 --json
.\cli.ps1 runs list
.\cli.ps1 runs list --page 1 --page-size 100 --json
.\cli.ps1 items download
.\cli.ps1 items download --item-id <item-id>
.\cli.ps1 items remove --dry-run
.\cli.ps1 items remove --item-id <item-id> --dry-run
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
  "outputRoot": "C:\\TimelineData\\video",
  "huggingFaceToken": "",
  "computeMode": "gpu"
}
```

## Safety

Source videos are read-only inputs. Current commands validate settings, check
configured paths, discover video files by path and extension, read ffprobe
metadata, extract bounded review frames with ffmpeg, run local OCR on generated
frame artifacts, and write generated audio evidence under `outputRoot`. They do
not modify, delete, copy, overwrite, recognize people/faces, call external
analysis APIs, or export source videos.

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
        frame_ocr.json
        audio_analysis.json
        activity_map.json
      artifacts/
        contact_sheet.jpg
        frames/
        ocr/
        audio/
```

`items refresh` runs the local evidence pipeline for changed videos: bounded
frame sampling, frame OCR, frame visual-feature extraction, audio derivative
analysis, TimelineForAudio-compatible audio models, activity mapping, and item
record refresh. The same stages are also exposed as smaller diagnostic
commands. `activity map` writes `raw_outputs/activity_map.json` with merged
audio activity, five-minute visual sentinel deltas, and inactive intervals that
can be skipped because no useful source signal was found. `process all` forces the same
pipeline over the selected batch. `serve` runs the changed-video refresh loop
continuously in the Docker worker.

`files list`, `items list`, and `runs list` accept `--page` and `--page-size`
for Timeline UI pagination. When pagination flags are omitted, they return all
rows as before.

`computeMode: "gpu"` is the default. In that mode, `start.ps1` and `cli.ps1`
layer `docker-compose.gpu.yml` on top of the default compose file. The
TimelineForAudio-compatible pyannote/ZIPA path must use the GPU worker and
CUDA/ONNX CUDA provider; it fails instead of silently falling back to CPU.
Frame OCR and frame visual features follow TimelineForImage and remain local
CPU processing.

The default Docker mounts cover the configured video roots on `C:\` and `F:\`
through `/mnt/c` and `/mnt/f` inside the worker.

The resident worker defaults to one changed item per refresh cycle through
`TIMELINE_FOR_VIDEO_WORKER_MAX_ITEMS=1`. Override that environment variable
when intentionally processing a larger batch.

`models list` reports an Audio-compatible `models` array and
`pipeline.generation_signature` for parent-product license/access display, plus
a Video `components` array for runtime readiness.
`--include-remote` fetches Hugging Face metadata such as license and gated
status. Frame OCR is executed locally with Tesseract. Audio derivative and
speech-candidate detection are executed locally with ffmpeg. The generated MP3
is a review artifact only; pyannote diarization and ZIPA acoustic-unit
extraction read a temporary normalized WAV so the audio model path matches
TimelineForAudio's preprocessing contract. Audio model execution is required by
default and fails the item instead of inventing speaker turns or phone tokens.
Diagnostic commands may still override execution mode for isolated
troubleshooting, but that mode is not stored in settings.

Milestone 6 export and removal commands are source-safe:

- `items download` writes a ZIP under `<outputRoot>\downloads\` and refreshes
  `<outputRoot>\latest\items.zip`. Use `--item-id` to export selected items.
- ZIP exports include generated item records, raw outputs, and artifacts only.
  They do not include source videos. The generated MP3 audio derivative is kept
  under `outputRoot` for local review and removal, but is not included in the
  ZIP export.
- `items remove --dry-run` reports generated artifacts that would be removed.
- `items remove --item-id <item-id>` removes selected generated item artifacts.
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

Operational docs:

- `docs/CLI.md`
- `docs/OUTPUTS.md`
- `docs/PIPELINE.md`
- `docs/RUNTIME.md`
- `docs/SAFETY.md`
- `docs/THIRD_PARTY_NOTICES.md`
- `docs/TESTING.md`
- `docs/VALIDATION_REPORT.md`
- `docs/VIDEO_REBUILD_TODO.md`
