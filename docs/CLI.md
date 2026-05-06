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
.\cli.ps1 settings save --input-root C:\TimelineData\input-video --output-root C:\TimelineData\video
```

`settings.json` is local runtime configuration and is not committed.

## Health And Discovery

```powershell
.\cli.ps1 health
.\cli.ps1 doctor
.\cli.ps1 files list
```

## Probe And Sampling

```powershell
.\cli.ps1 probe list --max-items 1
.\cli.ps1 sample frames --max-items 1 --samples-per-video 5
```

Sampling is bounded. It does not extract every frame.

## Items

```powershell
.\cli.ps1 items refresh --max-items 1
.\cli.ps1 items list
.\cli.ps1 items download
.\cli.ps1 items remove --dry-run
.\cli.ps1 items remove
```

- `items refresh` writes item JSON records and ffprobe raw output.
- `items list` reads generated item records.
- `items download` creates a source-safe ZIP and updates `latest`.
- `items remove --dry-run` reports generated artifacts that would be removed.
- `items remove` removes known generated artifacts only.

Most commands support `--json` for structured output.
