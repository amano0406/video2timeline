# CLI

Run commands from Windows PowerShell in `C:\apps\TimelineForVideo`.

```powershell
.\start.ps1
.\cli.ps1 <command>
.\stop.ps1
```

## Settings

```powershell
.\cli.ps1 settings init
.\cli.ps1 settings status
.\cli.ps1 settings save --input-root C:\Users\amano\Videos --input-root F:\Video --output-root C:\TimelineData\video
```

`settings.json` is local runtime configuration and is not committed.

## Health And Discovery

```powershell
.\cli.ps1 health
.\cli.ps1 doctor
.\cli.ps1 models list
.\cli.ps1 models list --include-remote --json
.\cli.ps1 files list
```

`models list` reports an Audio-compatible `models` array and
`pipeline.generation_signature` for parent-product license/access display,
plus Video runtime `components` for readiness checks.
Use `--include-remote` to fetch Hugging Face metadata such as license and gated
status. It is a visibility command; it does not process source videos.

## Probe And Sampling

```powershell
.\cli.ps1 probe list --max-items 1
.\cli.ps1 sample frames --max-items 1 --samples-per-video 5
.\cli.ps1 ocr frames --max-items 1
.\cli.ps1 audio analyze --max-items 1
.\cli.ps1 audio analyze --max-items 1 --audio-model-mode required
.\cli.ps1 activity map --max-items 1
.\cli.ps1 process all --max-items 1 --samples-per-video 5
```

Sampling is bounded. It does not extract every frame.

`ocr frames` runs local OCR over generated frame sample artifacts. `audio
analyze` writes source-safe generated audio evidence under `outputRoot`.
`audio analyze` requires the pyannote/ZIPA path by default and fails instead of
creating fallback speakers or phone tokens. Diagnostic commands may still use
`--audio-model-mode auto` or `--audio-model-mode off` for isolated
troubleshooting, but this is not saved in settings. Model execution uses a
temporary normalized WAV, not the review MP3 artifact. `computeMode: "gpu"` is
the default, and `cli.ps1` uses the GPU compose layer in that mode. `activity
map` writes `raw_outputs/activity_map.json` with merged audio activity,
five-minute visual sentinel deltas, and inactive intervals that can be skipped.
`process all` runs sampling, frame OCR, audio analysis, activity mapping, and
item refresh in one bounded command.

`process all` is a forced batch command. The normal product entrypoint is
`items refresh`.

## Items

```powershell
.\cli.ps1 items refresh --max-items 1
.\cli.ps1 items refresh --max-items 1 --samples-per-video 5 --audio-model-mode off
.\cli.ps1 items list
.\cli.ps1 items list --page 1 --page-size 100 --json
.\cli.ps1 items download
.\cli.ps1 items download --item-id <ITEM_ID>
.\cli.ps1 items remove --dry-run
.\cli.ps1 items remove --item-id <ITEM_ID> --dry-run
.\cli.ps1 items remove
```

- `items refresh` processes changed videos: bounded frame sampling, local frame
  OCR, generated audio evidence, required audio models by default, activity
  mapping, and final item records.
- `items list` reads generated item records. Use `--page` and `--page-size`
  for paged Timeline UI reads. Without them, all rows are returned.
- `items download` creates a source-safe ZIP and updates `latest`. Use
  `--item-id` repeatedly or comma-separated to include selected items.
- `items remove --dry-run` reports generated artifacts that would be removed.
- `items remove` removes known generated artifacts only. Use `--item-id`
  repeatedly or comma-separated to remove selected generated item artifacts.

## Worker Runs

```powershell
.\cli.ps1 runs list
.\cli.ps1 runs list --page 1 --page-size 100 --json
.\cli.ps1 runs show --run-id <RUN_ID>
.\cli.ps1 serve --once --json
```

`serve` is the resident worker command used by Docker. It repeats changed-video
refresh on an interval and records run state under the internal app-data area.
Failed pipeline steps are exposed as `failedSteps` in JSON run output and are
shown in worker logs.

Most commands support `--json` for structured output.

`files list` also accepts `--page` and `--page-size`:

```powershell
.\cli.ps1 files list --page 1 --page-size 100 --json
```
