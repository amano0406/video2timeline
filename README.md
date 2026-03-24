# video2timeline

`video2timeline` is a local-first tool that turns video files into timeline-oriented text for LLM workflows.

v1 is built around:

- `web/`: ASP.NET Core Razor Pages GUI
- `worker/`: Python batch worker
- `docker-compose.yml`: local orchestration
- file-based coordination through `request.json`, `status.json`, `result.json`, and `manifest.json`

## What It Does

- scans mounted video folders
- accepts multi-file uploads from the GUI
- writes one run directory per job
- keeps original video timestamps in the final timeline
- trims silence for ASR efficiency but stores `cut_map.json`
- runs OCR and image captioning only when the screen meaningfully changes
- emits `timeline.md` per media item plus LLM batch files

## Current v1 Defaults

- single `quality-first` profile
- CPU-first implementation
- GPU UI is intentionally not exposed yet
- diarization uses `pyannote` only when Hugging Face token and terms confirmation are available
- no `simple-diarizer`
- no clean transcript rewrite step

## Repo Layout

```text
video2timeline/
  configs/
  docker/
  docs/
  scripts/
  web/
  worker/
  docker-compose.yml
  start.bat
  start.command
  stop.bat
  stop.command
```

## Runtime Layout

Each job writes to a selected output root as:

```text
run-YYYYMMDD-HHMMSS-xxxx/
  request.json
  status.json
  result.json
  manifest.json
  RUN_INFO.md
  TRANSCRIPTION_INFO.md
  NOTICE.md
  logs/
    worker.log
  media/
    <media-id>/
      source.json
      audio/
        extracted.mp3
        trimmed.mp3
        cut_map.json
      transcript/
        raw.json
        raw.md
      screen/
        screenshot_01.jpg
        screenshots.jsonl
        screen_diff.jsonl
      timeline/
        timeline.md
  llm/
    timeline_index.jsonl
    batch-001.md
```

## Supported Video Extensions

Primary support:

- `.mp4`
- `.mov`
- `.m4v`
- `.avi`
- `.mkv`
- `.webm`

The actual decode path depends on `ffmpeg` / `ffprobe`.

## Prerequisites

For Docker usage:

- Windows or macOS
- Docker Desktop
- internet access for first-time image and model downloads

Optional:

- Hugging Face token for `pyannote`
- acceptance of the required gated model terms

## One-Click Style Startup

Windows:

```powershell
C:\apps\video2timeline\start.bat
```

macOS:

```bash
/Users/.../video2timeline/start.command
```

The scripts:

1. verify Docker is available
2. create `.env` from `.env.example` if needed
3. start `web` and `worker`
4. open `http://localhost:8090` by default

Stop:

```powershell
C:\apps\video2timeline\stop.bat
```

## Default Mounted Sources

`.env.example` assumes:

- `VIDEO_SOURCE_1=C:\Users\amano\Videos`
- `VIDEO_SOURCE_2=F:\Users\yutaro\Videos`
- `VIDEO_OUTPUT_ROOT=C:\apps\video2timeline\runs`
- `VIDEO2TIMELINE_WEB_PORT=8090`

These are mounted inside containers as:

- `/shared/inputs/amano`
- `/shared/inputs/yutaro`
- `/shared/outputs`

## GUI Pages

- `/`
  - complete setup first
  - upload files or choose a directory
  - create one job at a time
  - view the active job separately from completed jobs
  - download completed jobs as ZIP
- `/runs/{id}`
  - progress
  - ETA
  - log tail
  - generated timelines
- `/runs/{jobId}/{mediaId}`
  - rendered `timeline.md`
- `/settings`
  - Hugging Face token and terms flag
  - model approval links
  - approval status refresh

## Localization

- header language switch is available on all main pages
- current supported locales:
  - `ja`
  - `en`
  - `zh-CN`
  - `zh-TW`
  - `ko`
  - `es`
  - `fr`
  - `de`
  - `pt`
- browser language is used as the default when possible
- manual language selection is stored in a cookie
- supported languages and regional aliases are defined in [languages.json](C:/apps/video2timeline/web/Resources/Locales/languages.json)
- UI string dictionaries live in [Resources/Locales](C:/apps/video2timeline/web/Resources/Locales)

## API Endpoints

- `POST /api/scan`
- `POST /api/uploads`
- `POST /api/jobs`
- `GET /api/jobs/{id}`
- `POST /api/settings/huggingface`

## Worker CLI

Scan the configured mounted roots:

```powershell
$env:PYTHONPATH = "C:\apps\video2timeline\worker\src"
python -m video2timeline_worker scan --output C:\apps\video2timeline\runs\discovery.json
```

Process one specific job:

```powershell
$env:PYTHONPATH = "C:\apps\video2timeline\worker\src"
python -m video2timeline_worker run-job --job-dir C:\path\to\run-...
```

Run the polling daemon:

```powershell
$env:PYTHONPATH = "C:\apps\video2timeline\worker\src"
python -m video2timeline_worker daemon --poll-interval 5
```

## Notes

- silence trimming is an internal optimization; timelines remain based on original video time
- duplicate detection uses file hash and defaults to skip
- OCR is intentionally sparse; unchanged and minor-change frames are not expanded into full text
- `timeline.md` is the main LLM-facing artifact

See [APP_SPEC.md](C:/apps/video2timeline/docs/APP_SPEC.md) and [PIPELINE.md](C:/apps/video2timeline/docs/PIPELINE.md) for the current product shape.
