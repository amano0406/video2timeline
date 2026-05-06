# Runtime

The supported runtime path is Docker-first from Windows PowerShell.

```powershell
cd C:\apps\TimelineForVideo
.\start.ps1
.\cli.ps1 health
```

The worker image includes Python and ffmpeg/ffprobe. The compose service mounts:

- `C:\apps\TimelineForVideo` at `/workspace`
- `C:\` at `/mnt/c`
- Docker volumes for shared app data and cache

## Local Files

- `settings.json`: local runtime configuration, ignored by git.
- `settings.example.json`: committed template.
- `outputRoot`: configured output directory for generated artifacts.

## Health Check

```powershell
.\cli.ps1 health --json
```

The JSON output reports product, version, Python version, Docker status, and
settings path.
